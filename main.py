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

# Association table
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
async def read_root(request: Request, tag_filter: str = None):
    # Query tasks
    query = session.query(TodoItem)
    
    # Filter by tag if provided
    if tag_filter:
        tag = session.query(Tag).filter(Tag.name == tag_filter).first()
        if tag:
            query = query.filter(TodoItem.tags.contains(tag))
    
    # Separate incomplete and completed tasks
    incomplete_tasks = query.filter(TodoItem.is_completed == False).all()
    completed_tasks = query.filter(TodoItem.is_completed == True).all()
    tags = session.query(Tag).all()

    # Render the response
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
    tags: str = Form("")
):
    # Parse the due date if provided
    due_date_obj = datetime.datetime.strptime(due_date, '%Y-%m-%d') if due_date else None

    # Parse tags
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

    # Create a new todo item
    todo = TodoItem(title=title, body=body, due_date=due_date_obj)
    for tag_name in tag_list:
        tag = session.query(Tag).filter(Tag.name == tag_name).first()
        if not tag:
            tag = Tag(name=tag_name)
            session.add(tag)
        todo.tags.append(tag)

    session.add(todo)
    session.commit()

    # Query the updated incomplete and completed tasks
    incomplete_tasks = session.query(TodoItem).filter(TodoItem.is_completed == False).all()
    completed_tasks = session.query(TodoItem).filter(TodoItem.is_completed == True).all()

    # Return the updated lists
    return templates.TemplateResponse(
        "partials/task_lists.html",
        {
            "request": {},
            "incomplete_tasks": incomplete_tasks,
            "completed_tasks": completed_tasks,
        },
    )


@app.post("/toggle/{todo_id}", response_class=HTMLResponse)
async def toggle_completion(todo_id: int):
    # Find the task and toggle its status
    todo = session.query(TodoItem).filter(TodoItem.id == todo_id).first()
    if not todo:
        return HTMLResponse(content="Task not found", status_code=404)

    todo.is_completed = not todo.is_completed
    session.commit()

    # Get updated lists
    incomplete_tasks = session.query(TodoItem).filter(TodoItem.is_completed == False).all()
    completed_tasks = session.query(TodoItem).filter(TodoItem.is_completed == True).all()

    # Return both lists
    return templates.TemplateResponse(
        "partials/task_lists.html", 
        {
            "request": {}, 
            "incomplete_tasks": incomplete_tasks,
            "completed_tasks": completed_tasks
        }
    )


@app.get("/filter", response_class=HTMLResponse)
async def filter_tasks(tag_filter: str, completed: bool):
    query = session.query(TodoItem)
    
    # Filter tasks by tag
    tag = session.query(Tag).filter(Tag.name == tag_filter).first()
    if tag:
        query = query.filter(TodoItem.tags.contains(tag))
    
    # Filter by completion status
    query = query.filter(TodoItem.is_completed == completed)
    
    # Render only the list of tasks
    if completed:
        task_list = query.all()
        return templates.TemplateResponse(
            "partials/completed_tasks.html", {"request": {}, "completed_tasks": task_list}
        )
    else:
        task_list = query.all()
        return templates.TemplateResponse(
            "partials/incomplete_tasks.html", {"request": {}, "incomplete_tasks": task_list}
        )

@app.post("/delete/{todo_id}", response_class=HTMLResponse)
async def delete_task(todo_id: int):
    # Retrieve the task
    todo = session.query(TodoItem).filter(TodoItem.id == todo_id).first()
    if todo:
        session.delete(todo)
        session.commit()
    
    # Check if the list is now empty
    incomplete_tasks = session.query(TodoItem).filter(TodoItem.is_completed == False).all()
    completed_tasks = session.query(TodoItem).filter(TodoItem.is_completed == True).all()

    # Handle the specific case dynamically
    if not incomplete_tasks:
        return """
        <ul id="incomplete-list">
            <li>No incomplete tasks available.</li>
        </ul>
        """
    if not completed_tasks:
        return """
        <ul id="completed-list">
            <li>No completed tasks available.</li>
        </ul>
        """

    return ""  # Empty response for normal cases


@app.get("/filter-date", response_class=HTMLResponse)
async def filter_tasks_by_date(sort_by: str, completed: bool):
    query = session.query(TodoItem)

    # Filter by completion status
    query = query.filter(TodoItem.is_completed == completed)

    # Sort by creation date or due date
    if sort_by == "due_date":
        query = query.order_by(TodoItem.due_date)
    else:
        query = query.order_by(TodoItem.created_at)

    task_list = query.all()

    # Render appropriate partial template
    if completed:
        return templates.TemplateResponse(
            "partials/completed_tasks.html", {"request": {}, "completed_tasks": task_list}
        )
    else:
        return templates.TemplateResponse(
            "partials/incomplete_tasks.html", {"request": {}, "incomplete_tasks": task_list}
        )



# HTML templates and static files will go in the respective folders (not shown here for brevity).
