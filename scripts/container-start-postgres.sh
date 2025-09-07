container run -d \
  --name wirl-postgres \
  -e POSTGRES_DB=workflows \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres