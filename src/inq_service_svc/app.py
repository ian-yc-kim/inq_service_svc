from fastapi import FastAPI

app = FastAPI(debug=True, root_path=inq_service_svc)

# add routers