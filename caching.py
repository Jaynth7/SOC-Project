#Trying out redis for caching logs

# pyrefly: ignore [missing-import]
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

r.set('foo', 'bar')
# True

# bar
