import requests, json
#MEGLIO ESEGUIRE QUESTA QUERY SU http://localhost:8080/graphiql?flavor=transmode
URL = "http://localhost:8080/otp/transmodel/v3"

query = """
{
  __schema {
    types {
      name
      kind
      fields { name }
    }
  }
}
"""

r = requests.post(URL, json={"query": query})
data = r.json()

print(json.dumps(data, indent=2))