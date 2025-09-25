# Truy cập container backend
docker exec -it asset_backend bash

# Trong Python shell
python
>>> from app import create_app, db
>>> from models import User, UserRole
>>> app = create_app()
>>> with app.app_context():
...     admin = User(username='admin', email='admin@example.com', role=UserRole.ADMIN)
...     admin.set_password('admin123')
...     db.session.add(admin)
...     db.session.commit()