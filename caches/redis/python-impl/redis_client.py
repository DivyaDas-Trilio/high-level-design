import redis
from config import settings

redis_conf = settings.dev.redis
conn = redis.Redis(host=redis_conf.REDIS_HOST, port=redis_conf.REDIS_PORT)

# set key and get key.
conn.set("name", "Divya")
print(conn.get(name="name"))