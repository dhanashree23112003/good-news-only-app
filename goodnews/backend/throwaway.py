import requests

url = "https://dhanashree2311-news-sentiment-app.hf.space/run/predict"

response = requests.post(
    url,
    json={"data": ["This breakthrough could save millions of lives"]}
)

print("Status:", response.status_code)
print("Raw response:")
print(response.text)
