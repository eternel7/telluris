from fastapi.security import OAuth2PasswordBearer
from fastapi import FastAPI, Request, Depends, HTTPException
from jose import jwt, JWTError
from datetime import datetime, timedelta
from db.config import db, SECRET_KEY, ALGORITHM

ACCESS_TOKEN_EXPIRE_MINUTES = 240

def create_access_token(data: dict):
	to_encode = data.copy()
	expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
	to_encode.update({"exp": expire})
	encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
	return encoded_jwt
	
	
def get_current_user(request: Request):
	token = request.cookies.get("auth_token")
	if not token:
		return None

	try:
		# 2. Décoder le token pour obtenir le user_id
		try:
			payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
		except jwt.ExpiredSignatureError:
			raise HTTPException(status_code=401, detail="Token expired")
		except jwt.InvalidTokenError:
			raise HTTPException(status_code=401, detail="Invalid token")
			
		user_id: str = payload.get("user_id")
		
		user_doc = db.get(user_id)
		if not user_doc or user_doc is None:
			return None
		
		# clean up before share to any other function
		user_doc.pop("password", None)
		user_doc.pop("token", None)
		return user_doc
		
	except JWTError:
		return None