import os

import pika
import json

from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from openai import OpenAI

# Load environment variables.
load_dotenv()

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
RABBITMQ_PORT = os.getenv('RABBITMQ_PORT')
RABBITMQ_USER = os.getenv('RABBITMQ_USER')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS')

RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE')
RABBITMQ_EXCHANGE = os.getenv('RABBITMQ_EXCHANGE')
RABBITMQ_ROUTING_KEY = os.getenv('RABBITMQ_ROUTING_KEY')

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL")
ELASTICSEARCH_API_KEY = os.getenv("ELASTICSEARCH_API_KEY")
ELASTICSEARCH_LEGAL_DOCUMENT_INDEX = os.getenv("ELASTICSEARCH_LEGAL_DOCUMENT_INDEX")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize Elasticsearch client.
es_client = Elasticsearch(
    hosts=ELASTICSEARCH_URL,
    api_key=ELASTICSEARCH_API_KEY
)

# Initialize OpenAI client.
openai_client = OpenAI(api_key=OPENAI_API_KEY)


def search_elasticsearch(query, size=5):
    """
    Search for relevant documents in Elasticsearch.
    """

    search_result = es_client.search(
        index=ELASTICSEARCH_LEGAL_DOCUMENT_INDEX,
        size=size,
        query={
            "function_score": {
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"title": query}},
                            {"match": {"jenis_bentuk_peraturan": query}},
                            {"match": {"tentang": query}},
                            {"match": {"content_text": query}},
                            {
                                "nested": {
                                    "path": "dasar_hukum",
                                    "query": {
                                        "match": {"dasar_hukum.title": query}
                                    }
                                }
                            },
                            {
                                "nested": {
                                    "path": "mengubah",
                                    "query": {
                                        "match": {"mengubah.title": query}
                                    }
                                }
                            },
                            {
                                "nested": {
                                    "path": "diubah_oleh",
                                    "query": {
                                        "match": {"diubah_oleh.title": query}
                                    }
                                }
                            },
                            {
                                "nested": {
                                    "path": "mencabut",
                                    "query": {
                                        "match": {"mencabut.title": query}
                                    }
                                }
                            },
                            {
                                "nested": {
                                    "path": "dicabut_oleh",
                                    "query": {
                                        "match": {"dicabut_oleh.title": query}
                                    }
                                }
                            },
                            {
                                "nested": {
                                    "path": "melaksanakan_amanat_peraturan",
                                    "query": {
                                        "match": {"melaksanakan_amanat_peraturan.title": query}
                                    }
                                }
                            },
                            {
                                "nested": {
                                    "path": "dilaksanakan_oleh_peraturan_pelaksana",
                                    "query": {
                                        "match": {"dilaksanakan_oleh_peraturan_pelaksana.title": query}
                                    }
                                }
                            },
                        ]
                    }
                },
                "functions": [
                    {
                        "linear": {
                            "ditetapkan_tanggal": {
                                "origin": "now",
                                "scale": "365d",
                                "offset": "365d",
                                "decay": 0.5
                            }
                        }
                    },
                    {
                        "filter": {"term": {"jenis_bentuk_peraturan": "UNDANG-UNDANG DASAR"}},
                        "weight": 2.4
                    },
                    {
                        "filter": {"term": {"jenis_bentuk_peraturan": "KETETAPAN MAJELIS PERMUSYAWARATAN RAKYAT"}},
                        "weight": 2.2
                    },
                    {
                        "filter": {"term": {"jenis_bentuk_peraturan": "UNDANG-UNDANG"}},
                        "weight": 2.0
                    },
                    {
                        "filter": {"term": {"jenis_bentuk_peraturan": "PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG"}},
                        "weight": 2.0
                    },
                    {
                        "filter": {"term": {"jenis_bentuk_peraturan": "PERATURAN PEMERINTAH"}},
                        "weight": 1.8
                    },
                    {
                        "filter": {"term": {"jenis_bentuk_peraturan": "PERATURAN PRESIDEN"}},
                        "weight": 1.6
                    },
                    {
                        "filter": {"term": {"jenis_bentuk_peraturan": "PERATURAN MENTERI"}},
                        "weight": 1.4
                    },
                    {
                        "filter": {"term": {"jenis_bentuk_peraturan": "PERATURAN DAERAH"}},
                        "weight": 1.2
                    },
                    {
                        "filter": {"term": {"jenis_bentuk_peraturan": "PERATURAN BADAN/LEMBAGA"}},
                        "weight": 1.0
                    },
                ],
                "boost_mode": "avg"
            }
        },

        source={
            "includes": [
                "content_text"
            ]
        },
    )

    # Extract content from hits
    documents = [
        hit["_source"]["content_text"][0] for hit in search_result["hits"]["hits"]
    ]

    return documents


def retrieval_augmented_generation(query, documents):
    """
    Use OpenAI API to generate a response augmented with retrieved documents.
    """
    doc_str_list = []
    for doc in documents:
        doc_str = ' '.join(doc)
        doc_str_list.append(doc_str)

    # Combine documents into a single context
    prompt = (f"Answer the question with these additional legal documents context if they are relevant:\n\n"
              f"{documents}\n\n"
              f"Question: {query}\n\n"
              f"Answer:")

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that answers question about laws in Indonesia. "
                           "Respond using Indonesian language"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return completion.choices[0].message.content


def process_message(message):
    query = message['question']
    print("Processing question:", query)

    # Retrieve relevant documents.
    documents = search_elasticsearch(query)

    # Generate response with OpenAI.
    inference = retrieval_augmented_generation(query, documents)

    # Prepare response.
    processed_message = {"answer": inference}
    print("Answered question:", query)

    return processed_message


def callback(ch, method, properties, body):
    # Deserialize and process the message
    message = json.loads(body)
    processed_message = process_message(message)

    # Send the response back to the reply_to queue if it exists
    if properties.reply_to:
        ch.basic_publish(
            exchange="",
            routing_key=properties.reply_to,
            body=json.dumps(processed_message),
            properties=pika.BasicProperties(correlation_id=properties.correlation_id)
        )

    # Acknowledge the message
    ch.basic_ack(delivery_tag=method.delivery_tag)


def consume_messages():
    credentials = pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials)
    connection = pika.BlockingConnection(parameters)

    channel = connection.channel()

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

    print("Waiting for messages. To exit press CTRL+C")
    channel.start_consuming()


if __name__ == "__main__":
    consume_messages()

