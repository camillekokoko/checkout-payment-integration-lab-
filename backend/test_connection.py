from app.checkout_client import CheckoutClient

client = CheckoutClient();
response = client.get_payment("pay_test123")
print("HTTP Status:", response.status_code)
print("Response Body:", response.text)
print("Request URL:", response.request.url)
print("Content Type:", response.headers.get("content-type"))
print("Response Length:", len(response.content))
print("Request ID:", response.headers.get("cko-request-id"))