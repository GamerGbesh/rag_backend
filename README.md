# RAG Education System Backend

A Django-based education platform that combines document management with AI-powered Retrieval-Augmented Generation (RAG) capabilities. Users can create libraries, organize documents by courses, and interact with an AI assistant that can answer questions based on uploaded content.

## Features

- **User Authentication**: JWT-based authentication with registration, login, and logout
- **Library Management**: Create and manage educational libraries with configurable access
- **Course Organization**: Organize documents into courses within libraries
- **Document Upload**: Support for multiple file formats (PDF, DOCX, TXT, PPTX, Images)
- **AI-Powered Q&A**: Query documents using LangChain-powered RAG system
- **Quiz Generation**: Automatically generate quizzes from document content
- **Role-Based Access**: Library creators, admins, and members with different permissions
- **Vector Database**: ChromaDB integration for semantic document search

## Tech Stack

- **Backend**: Django 5.1.4 + Django REST Framework
- **Database**: PostgreSQL (configurable)
- **Vector Database**: ChromaDB with HNSWLIB
- **AI/ML**: LangChain, OpenAI, Anthropic, Ollama, HuggingFace
- **Authentication**: JWT (SimpleJWT)
- **File Processing**: PyMuPDF, python-pptx, pytesseract
- **Other**: CORS headers for frontend integration

## Prerequisites

- Python 3.11+
- PostgreSQL
- UV package manager (recommended) or pip

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/GamerGbesh/rag_backend.git
   cd backend
   ```

2. **Install dependencies**
   ```bash
   # Using UV (recommended)
   uv sync
   
   # Or using pip
   pip install -r requirements.txt
   ```

3. **Environment Setup**
   Create a `.env` file in the project root:
   ```env
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   DATABASE_URL=postgresql://postgres:password@localhost:5432/rag
   
   # I used ollama locally but if you want to use OPENAI or ANTRHOPIC modify as necessary and install the necessary packages
   # AI Provider API Keys
   OPENAI_API_KEY=your-openai-key
   ANTHROPIC_API_KEY=your-anthropic-key
   ```

4. **Database Setup**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Create Superuser** (optional)
   ```bash
   python manage.py createsuperuser
   ```

6. **Run the Server**
   ```bash
   python manage.py runserver
   ```

The API will be available at `http://localhost:8000`

## API Documentation

### Authentication Endpoints

#### Register User
- **POST** `/auth/signup/`
- **Body**:
  ```json
  {
    "username": "user123",
    "email": "user@example.com",
    "password": "password123",
    "password2": "password123"
  }
  ```
- **Response**: JWT tokens (access & refresh)

#### Login
- **POST** `/auth/login/`
- **Body**:
  ```json
  {
    "username": "user123",
    "password": "password123"
  }
  ```
- **Response**: JWT tokens

#### Logout
- **POST** `/auth/logout/`
- **Headers**: `Authorization: Bearer <access_token>`

#### Token Refresh
- **POST** `/auth/api/token/refresh/`
- **Body**:
  ```json
  {
    "refresh": "<refresh_token>"
  }
  ```

### Library Management

#### Create Library
- **POST** `/createLibrary`
- **Headers**: `Authorization: Bearer <access_token>`
- **Body**:
  ```json
  {
    "library_name": "My Library",
    "library_description": "Description of the library",
    "entry_key": "optional_entry_key",
    "joinable": true
  }
  ```

#### Join Library
- **POST** `/joinLibrary`
- **Headers**: `Authorization: Bearer <access_token>`
- **Body**:
  ```json
  {
    "library_name": "Library Name",
    "entry_key": "entry_key"
  }
  ```

#### Get Libraries
- **GET** `/Libraries`
- **Headers**: `Authorization: Bearer <access_token>`
- **Response**: User's libraries and joined libraries

#### Delete Library
- **DELETE** `/deleteLibrary`
- **Headers**: `Authorization: Bearer <access_token>`
- **Body**:
  ```json
  {
    "library_id": 1
  }
  ```

### Course Management

#### Add Course
- **POST** `/Courses`
- **Headers**: `Authorization: Bearer <access_token>`
- **Body**:
  ```json
  {
    "library_id": 1,
    "course_name": "Course Name",
    "course_description": "Course description"
  }
  ```

#### Get Courses
- **GET** `/getCourses?library_id=1`
- **Headers**: `Authorization: Bearer <access_token>`

#### Delete Course
- **DELETE** `/Courses`
- **Headers**: `Authorization: Bearer <access_token>`
- **Body**:
  ```json
  {
    "library_id": 1,
    "course_id": 1
  }
  ```

### Document Management

#### Upload Document
- **POST** `/Documents`
- **Headers**: `Authorization: Bearer <access_token>`
- **Content-Type**: `multipart/form-data`
- **Body**:
  ```
  course_id: 1
  file: <file_upload>
  ```
- **Supported formats**: PDF, DOCX, TXT, PPTX, JPEG, JPG, PNG
- **Max size**: 3MB

#### Get Documents
- **GET** `/getDocuments?course_id=1&library_id=1`
- **Headers**: `Authorization: Bearer <access_token>`

#### Delete Document
- **DELETE** `/deleteDocuments`
- **Headers**: `Authorization: Bearer <access_token>`
- **Body**:
  ```json
  {
    "doc_id": 1
  }
  ```

### AI-Powered Features

#### Query Documents (RAG)
- **GET** `/question?query=your_question&course_id=1`
- **Headers**: `Authorization: Bearer <access_token>`
- **Response**:
  ```json
  {
    "LLM_response": "AI-generated answer based on course documents"
  }
  ```

#### Generate Quiz
- **GET** `/quiz?document_id=1&number_of_questions=5`
- **Headers**: `Authorization: Bearer <access_token>`
- **Response**: Generated quiz questions

### Member Management

#### Get Members
- **GET** `/getMembers?library_id=1`
- **Headers**: `Authorization: Bearer <access_token>`

#### Remove Member (Creator only)
- **DELETE** `/removeMember`
- **Headers**: `Authorization: Bearer <access_token>`
- **Body**:
  ```json
  {
    "library_id": 1,
    "user_id": 2
  }
  ```

#### Leave Library
- **DELETE** `/leaveLibrary`
- **Headers**: `Authorization: Bearer <access_token>`
- **Body**:
  ```json
  {
    "library_id": 1
  }
  ```

#### Manage Admins (Creator only)
- **POST/DELETE** `/Admins`
- **Headers**: `Authorization: Bearer <access_token>`
- **Body**:
  ```json
  {
    "library_id": 1,
    "user_id": 2
  }
  ```

## Permissions & Roles

### User Roles
- **Creator**: Library owner with full permissions
- **Admin**: Can manage courses and documents
- **Member**: Can view content and query AI

### Permission Matrix
| Action | Creator | Admin | Member |
|--------|---------|-------|--------|
| Create/Delete Library | ✅ | ❌ | ❌ |
| Add/Remove Members | ✅ | ❌ | ❌ |
| Manage Admins | ✅ | ❌ | ❌ |
| Add/Delete Courses | ✅ | ✅ | ❌ |
| Upload/Delete Documents | ✅ | ✅ | ❌ |
| Query AI | ✅ | ✅ | ✅ |
| Generate Quiz | ✅ | ✅ | ✅ |
| View Content | ✅ | ✅ | ✅ |

## Limits & Constraints

- **Libraries per user**: 3 (including 1 private + 2 joinable)
- **Members per library**: 15
- **Admins per library**: 3
- **Courses per library**: 3
- **Documents per course**: 5
- **File size limit**: 3MB
- **Supported file types**: PDF, DOCX, TXT, PPTX, JPEG, JPG, PNG

## Configuration

### Database Configuration
Update `backend/settings.py` for your database:
```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "your_db_name",
        "USER": "your_db_user",
        "PASSWORD": "your_db_password",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
```

### CORS Configuration
Configure allowed origins in `settings.py`:
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Your frontend URL
    "http://localhost:3000",
]
```

### AI Provider Configuration
The system supports multiple AI providers. Configure your preferred provider's API keys in environment variables.

## Development

### Running Tests
```bash
python manage.py test
```

### Django Admin
Access the admin interface at `http://localhost:8000/admin/` with your superuser credentials.

### File Storage
Uploaded documents are stored in `media/documents/YYYY/MM/DD/` directory structure.

## Deployment

1. Set `DEBUG=False` in production
2. Configure proper database credentials
3. Set up static file serving
4. Configure environment variables for API keys
5. Set up HTTPS and proper CORS origins

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

<!-- ## License

[Add your license information here] -->

## Support

For questions or issues, please [create an issue](https://github.com/GamerGbesh/rag_backend/issues) or contact [me](gbesh.12@gmail.com).