from app import create_app
from sqlalchemy.exc import OperationalError

app = create_app()

@app.route('/boom')
def boom():
    raise RuntimeError('forced')

@app.route('/dbboom')
def dbboom():
    raise OperationalError('statement', None, Exception('db down'))

client = app.test_client()
r1 = client.get('/boom')
r2 = client.get('/dbboom')
body1 = r1.get_data(as_text=True)
body2 = r2.get_data(as_text=True)
print('boom', r1.status_code, 'contains_erro', 'Estamos enfrentando problemas técnicos' in body1)
print('dbboom', r2.status_code, 'contains_erro', 'Estamos enfrentando problemas técnicos' in body2)
