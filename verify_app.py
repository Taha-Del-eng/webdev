from app import app

client = app.test_client()
response = client.get('/')
print('status=', response.status_code)
print('template_ok=', '<title>NavyMart' in response.get_data(as_text=True))
print('product_count=', response.get_data(as_text=True).count('class="item"'))
print(response.get_data(as_text=True)[:160])
