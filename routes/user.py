from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
import bcrypt
import uuid
from jose import jwt
from db.config import db

user_router = APIRouter()
SECRET_KEY = "17c94c78a181b6fd3fac8ccdbb43754b3a55a73fd47fcee0cf21ca59d2571f98-supersecret"
ALGORITHM = "HS256"

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    password_again: str
    user_type: str

class LoginRequest(BaseModel):
    email: str
    password: str

@user_router.post("/register")
async def register_user(user: RegisterRequest):
    user_doc = db.get("user:"+user.email)
    if user_doc:
        raise HTTPException(status_code=400, detail="User already exists")
	if password_again===password:
		hashed_pw = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
		user_id = str(uuid.uuid4())
		token = jwt.encode({"user_id": user_id}, SECRET_KEY, algorithm=ALGORITHM)

		db.put({
			"_id": "user:"+user.email,
			"username": user.username,
			"email": user.email,
			"password": hashed_pw.decode(),
			"token": token,
		})

    return {"token": token, "user_id": user_id, "username": user.username}

@user_router.post("/login")
async def login_user(user: LoginRequest):
    users_collection = db["users"]
    found_user = users_collection.find_one({"email": user.email})

    if not found_user or not bcrypt.checkpw(user.password.encode(), found_user["password"].encode()):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    token = jwt.encode({"user_id": found_user["user_id"]}, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token, "user_id": found_user["user_id"], "user_type": found_user["user_type"]}