from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Table, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
from typing import List

# Database setup
DATABASE_URL = "sqlite:///./todo.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()

# Models
class TodoItem(Base):
    __tablename__ = "todo_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    body = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    tags = relationship("Tag", secondary="todo_tags", back_populates="todos")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    todos = relationship("TodoItem", secondary="todo_tags", back_populates="tags")


todo_tags = Table(
    "todo_tags",
    Base.metadata,
    Column("todo_id", Integer, ForeignKey("todo_items.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)

# Create tables
Base.metadata.create_all(bind=engine)

# App setup
app = FastAPI()

# Templates setup
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    incomplete_tasks = session.query(TodoItem).filter(TodoItem.is_completed == False).all()
    completed_tasks = session.query(TodoItem).filter(TodoItem.is_completed == True).all()
    tags = session.query(Tag).all()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "incomplete_tasks": incomplete_tasks,
            "completed_tasks": completed_tasks,
            "tags": tags,
        },
    )


@app.post("/add", response_class=HTMLResponse)
async def add_todo(
    title: str = Form(...),
    body: str = Form(""),
    due_date: str = Form(""),
    tags: str = Form(""),
):
    due_date_obj = datetime.datetime.strptime(due_date, "%Y-%m-%d") if due_date else None
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

    todo = TodoItem(title=title, body=body, due_date=due_date_obj)
    for tag_name in tag_list:
        tag = session.query(Tag).filter(Tag.name == tag_name).first()
        if not tag:
            tag = Tag(name=tag_name)
            session.add(tag)
        todo.tags.append(tag)

    session.add(todo)
    session.commit()

    incomplete_tasks = session.query(TodoItem).filter(TodoItem.is_completed == False).all()
    completed_tasks = session.query(TodoItem).filter(TodoItem.is_completed == True).all()
    tags = session.query(Tag).all()

    return templates.TemplateResponse(
        "partials/task_lists.html",
        {
            "request": {},
            "incomplete_tasks": incomplete_tasks,
            "completed_tasks": completed_tasks,
            "tags": tags,
        },
    )


@app.post("/toggle/{todo_id}", response_class=HTMLResponse)
async def toggle_completion(todo_id: int):
    todo = session.query(TodoItem).filter(TodoItem.id == todo_id).first()
    if todo:
        todo.is_completed = not todo.is_completed
        session.commit()

    incomplete_tasks = session.query(TodoItem).filter(TodoItem.is_completed == False).all()
    completed_tasks = session.query(TodoItem).filter(TodoItem.is_completed == True).all()
    tags = session.query(Tag).all()

    return templates.TemplateResponse(
        "partials/task_lists.html",
        {
            "request": {},
            "incomplete_tasks": incomplete_tasks,
            "completed_tasks": completed_tasks,
            "tags": tags,
        },
    )


@app.post("/delete/{todo_id}", response_class=HTMLResponse)
async def delete_task(todo_id: int):
    todo = session.query(TodoItem).filter(TodoItem.id == todo_id).first()
    if todo:
        session.delete(todo)
        session.commit()

    incomplete_tasks = session.query(TodoItem).filter(TodoItem.is_completed == False).all()
    completed_tasks = session.query(TodoItem).filter(TodoItem.is_completed == True).all()
    tags = session.query(Tag).all()

    return templates.TemplateResponse(
        "partials/task_lists.html",
        {
            "request": {},
            "incomplete_tasks": incomplete_tasks,
            "completed_tasks": completed_tasks,
            "tags": tags,
        },
    )


@app.get("/filter-by-tag", response_class=HTMLResponse)
async def filter_by_tag(request: Request, tag_name: str, completed: bool = None):
    query = session.query(TodoItem).join(TodoItem.tags).filter(Tag.name == tag_name)

    if completed is not None:
        query = query.filter(TodoItem.is_completed == completed)

    filtered_tasks = query.all()
    tags = session.query(Tag).all()

    return templates.TemplateResponse(
        "partials/task_lists.html",
        {
            "request": request,
            "incomplete_tasks": [task for task in filtered_tasks if not task.is_completed],
            "completed_tasks": [task for task in filtered_tasks if task.is_completed],
            "tags": tags,
        },
    )
