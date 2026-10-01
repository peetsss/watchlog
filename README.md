# watchlog

**watchlog** is a web application that allows users to create groups, add movies to a watchlist, and rate them. The application utilizes the TMDB API to gather detailed information about the movies.

## Technologies Used
- Django Framework
- Bootstrap 5
- PostgreSQL
- Docker
- Docker-compose
- GitHub Actions

## Example images
### Index
![Index View](images/index.png)

### Group
![Group View](images/group.png)

## Getting Started

### Prerequisites
Before you begin, ensure you have Docker and Docker Compose installed on your machine.

### Setting Up the Environment

**Create a `.env.dev` file**:

Create a file named `.env.dev` in the root directory of the project and add the following variables. Replace the placeholders with your actual values:

   ```plaintext
   DJANGO_KEY=your_django_key

   DEBUG=true
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

   TMDB_API_KEY=your_tmdb_api_key

   POSTGRES_USER=postgres_user
   POSTGRES_PASSWORD=postgres_password
   POSTGRES_DB=watchlog_db
   POSTGRES_HOST=db
   POSTGRES_PORT=5432
   ```

### Running the Application
To run the application, use:
```
just dev
```

To run all tests or tests of a certain app, use:
```
just test
just test -- movies
```
