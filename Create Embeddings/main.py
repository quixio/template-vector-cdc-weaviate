from quixstreams import Application
from sentence_transformers import SentenceTransformer
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Application(
    consumer_group="vectorsv1",
    auto_offset_reset="earliest",
    auto_create_topics=True,  # Quix app has an option to auto create topics
)

# Define input and ouput topics with JSON deserializer
input_topic = app.topic(os.environ['input'], value_deserializer="json")
output_topic = app.topic(os.environ['output'], value_serializer="json")

def simplify_data(row):

    # Creating a new dictionary that includes 'kind' and zips column names with values
    new_structure = {"kind": row["kind"],"table": row["table"]}
    new_structure.update({key: value for key, value in zip(row["columnnames"], row["columnvalues"])})

    # Optionally converting integers to strings
    new_structure["year"] = str(new_structure["year"])

    return new_structure

encoder = SentenceTransformer('all-MiniLM-L6-v2') # Model to create embeddings

# Define the embedding function
def create_embeddings(row):
    text = row['description']
    embeddings = encoder.encode(text)
    embedding_list = embeddings.tolist() # Conversion step because SentenceTransformer outputs a numpy Array but Qdrant expects a plain list
    print(f'Created vector: "{embedding_list}"')

    return embedding_list

# Initialize a streaming dataframe based on the stream of messages from the input topic:
sdf = app.dataframe(topic=input_topic)

sdf = sdf.filter(lambda data: data["table"] == "books")
sdf = sdf.update(lambda val: logger.info(f"Original data: {val}"))

sdf = sdf.apply(simplify_data)
sdf = sdf.update(lambda val: logger.info(f"Received update: {val}"))

# Trigger the embedding function for any new messages(rows) detected in the filtered SDF
sdf["embeddings"] = sdf.apply(create_embeddings, stateful=False)

# Update the timestamp column to the current time in nanoseconds
sdf["Timestamp"] = sdf.apply(lambda row: time.time_ns())

# Publish the processed SDF to a Kafka topic specified by the output_topic object.
sdf = sdf.to_topic(output_topic)

app.run(sdf)