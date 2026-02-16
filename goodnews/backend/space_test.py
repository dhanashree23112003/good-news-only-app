
from gradio_client import Client

client = Client("dhanashree2311/news-sentiment-app")

result = client.predict(
    "This breakthrough could save millions of lives",
    api_name="/predict"
)

print(result)
