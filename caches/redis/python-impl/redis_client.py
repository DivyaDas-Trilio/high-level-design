import redis
from requests import session
#from config import settings

#redis_conf = settings.default.redis

def create_connection():
    conn = redis.Redis(host="172.26.0.56", port=30079)
    return conn

if __name__ == '__main__':
    conn = create_connection() 
    # set key and get key.
    # conn.set("session", "SeSsIoN", nx=True, ex=20)
    # conn.set("session", "SeSsIo", ex=20)
    
    # print(conn.get(name="session"))
    
    # List operation on.
    conn.lpush('session', 10,20)
    print(conn.lrange(name=session, start=0, end=-1))