# User Management API

Base URL: `http://localhost:8080/api`

## Endpoints

### Health Check
- `GET /` - Service health check

### Users

#### List Users
- `GET /users?page=1&per_page=20` - Get paginated list of users

#### Search Users
- `GET /users/search?q=john&page=1&per_page=20` - Search users by name

#### Get User
- `GET /users/{id}` - Get user by ID

#### Create User
- `POST /users` - Create new user
```json
{
  "name": "John Doe",
  "comment": "Admin user",
  "telegram_id": 123456789
}
```

#### Update User  
- `PUT /users/{id}` - Update user by ID
```json
{
  "name": "Jane Doe",
  "comment": null,
  "telegram_id": 987654321
}
```

#### Delete User
- `DELETE /users/{id}` - Delete user by ID

## Response Format

### User Object
```json
{
  "id": "uuid",
  "name": "string",
  "comment": "string|null", 
  "telegram_id": "number|null",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### Users List Response
```json
{
  "users": [UserObject],
  "total": 100,
  "page": 1,
  "per_page": 20
}
```

## Status Codes
- `200` - Success
- `201` - Created
- `404` - Not Found
- `409` - Conflict (duplicate telegram_id)
- `500` - Internal Server Error