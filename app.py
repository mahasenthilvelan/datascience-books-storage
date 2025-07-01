import streamlit as st
import base64
import bcrypt
from pymongo import MongoClient
from datetime import datetime, time
import pandas as pd
import plotly.express as px
from bson import ObjectId
import socket
import gridfs
import re

# ✅ Correct rerun function
def rerun():
    st.experimental_rerun()

# --- MongoDB Setup ---
db_password = st.secrets["mongodb"]["password"]  # only password in secrets
admin_user = st.secrets["mongodb"]["admin_user"]
admin_pass = st.secrets["mongodb"]["admin_pass"]

mongo_uri = f"mongodb+srv://DATASCIENCE:{db_password}@datasciencebooks.nvf4l48.mongodb.net/?retryWrites=true&w=majority&appName=Datasciencebooks"

client = MongoClient(mongo_uri)
db = client["library"]
books_col = db["books"]
users_col = db["users"]
logs_col = db["logs"]
fav_col = db["favorites"]
fs = gridfs.GridFS(db)

# --- Utility Functions ---
def get_ip():
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except:
        return "unknown"

def safe_key(raw_key):
    """Sanitize dynamic keys for Streamlit widgets."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', str(raw_key))

# --- Registration ---
def register_user():
    st.subheader("🌽 Register")
    username = st.text_input("Username", key="reg_username")
    password = st.text_input("Password", type="password", key="reg_password")
    if st.button("Register"):
        if users_col.find_one({"username": username}):
            st.error("Username already exists")
        else:
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            users_col.insert_one({
                "username": username,
                "password": hashed_pw,
                "verified": True,
                "created_at": datetime.utcnow()
            })
            st.success("Registered successfully")

# --- Login ---
def login_user():
    st.subheader("🔐 Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login"):
        if username == admin_user and password == admin_pass:
            st.session_state["user"] = "admin"
            st.success("Logged in as Admin")
            rerun()
        else:
            user = users_col.find_one({"username": username})
            if user and user.get("verified") and bcrypt.checkpw(password.encode(), user["password"]):
                st.session_state["user"] = username
                st.success(f"Welcome {username}")
                rerun()
            else:
                st.error("Invalid or unverified credentials")

# --- Upload Book ---
def upload_book():
    st.subheader("📄 Upload Book")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf", key="upload_pdf")
    if uploaded_file:
        title = st.text_input("Title", value=uploaded_file.name.rsplit('.', 1)[0], key="upload_title")
        author = st.text_input("Author", key="upload_author")
        language = st.text_input("Language", key="upload_language")
        keywords = st.text_input("Keywords (comma-separated)", key="upload_keywords")
        course_options = [
            "Probability & Statistics using R", "Mathematics for Data Science",
            "Python for Data Science", "RDBMS, SQL & Visualization",
            "Data Mining Techniques", "Artificial Intelligence & Reasoning",
            "Machine Learning", "Big Data Mining & Analytics",
            "Predictive Analytics", "Ethics & Data Security",
            "Applied Spatial Data Analytics Using R", "Machine Vision",
            "Deep Learning & Applications", "Generative AI with LLMs",
            "Social Networks & Graph Analysis", "Data Visualization Techniques",
            "Algorithmic Trading", "Bayesian Data Analysis",
            "Healthcare Data Analytics", "Data Science for Structural Biology",
            "Other / Not Mapped"
        ]
        course = st.selectbox("Course", course_options, key="upload_course")
        if st.button("Upload", key="upload_button"):
            data = uploaded_file.read()
            if len(data) == 0:
                st.error("File is empty")
                return
            file_id = fs.put(data, filename=uploaded_file.name)
            books_col.insert_one({
                "title": title,
                "author": author,
                "language": language,
                "course": course if course else "Other / Not Mapped",
                "keywords": [k.strip().lower() for k in keywords.split(",") if k.strip()],
                "file_id": file_id,
                "file_name": uploaded_file.name,
                "uploaded_at": datetime.utcnow()
            })
            st.success("Book uploaded")

# --- Admin Dashboard ---
def admin_dashboard():
    st.subheader("📊 Admin Analytics")
    total_views = logs_col.count_documents({})
    total_downloads = logs_col.count_documents({"type": "download"})
    st.metric("Total Activity", total_views)
    st.metric("Total Downloads", total_downloads)
    logs = list(logs_col.find())
    if logs:
        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        st.dataframe(df[['user', 'book', 'timestamp', 'type']])
    st.write("### 📚 Books Uploaded per Course")
    course_stats = books_col.aggregate([
        {"$group": {"_id": "$course", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ])
    course_data = [{"Course": row["_id"], "Count": row["count"]} for row in course_stats]
    if course_data:
        df = pd.DataFrame(course_data)
        st.dataframe(df)
        fig = px.bar(df, x="Course", y="Count", title="Books per Course")
        st.plotly_chart(fig)

# --- User Dashboard ---
def user_dashboard(user):
    st.subheader("📊 Your Dashboard")
    logs = list(logs_col.find({"user": user}))
    favs = list(fav_col.find({"user": user}))
    if logs:
        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        st.dataframe(df[['book', 'author', 'language', 'timestamp']])
    if favs:
        st.write("⭐ Bookmarked Books")
        book_ids = [ObjectId(f['book_id']) for f in favs]
        books = books_col.find({"_id": {"$in": book_ids}})
        for book in books:
            st.write(f"📘 {book['title']} by {book.get('author', 'Unknown')}")

# --- Search Books ---
def search_books():
    st.subheader("🔎 Search Books")

    with st.form("search_form"):
        with st.expander("🔧 Advanced Search Filters", expanded=True):
            title = st.text_input("Title", key="search_title")
            author = st.text_input("Author", key="search_author")
            keyword_input = st.text_input("Keywords (any match)", key="search_keywords")

            languages = [l for l in books_col.distinct("language") if l and l.strip()]
            existing_courses = books_col.distinct("course")
            default_courses = [
                "Probability & Statistics using R", "Mathematics for Data Science",
                "Python for Data Science", "RDBMS, SQL & Visualization",
                "Data Mining Techniques", "Artificial Intelligence & Reasoning",
                "Machine Learning", "Big Data Mining & Analytics",
                "Predictive Analytics", "Ethics & Data Security",
                "Applied Spatial Data Analytics Using R", "Machine Vision",
                "Deep Learning & Applications", "Generative AI with LLMs",
                "Social Networks & Graph Analysis", "Data Visualization Techniques",
                "Algorithmic Trading", "Bayesian Data Analysis",
                "Healthcare Data Analytics", "Data Science for Structural Biology",
                "Other / Not Mapped"
            ]
            all_courses = sorted(set(default_courses + existing_courses))

            course_filter = st.selectbox("Course", ["All"] + all_courses, key="search_course")
            language_filter = st.selectbox("Language", ["All"] + sorted(languages), key="search_language")

        submitted = st.form_submit_button("🔍 Search")

    query = {}
    filters_applied = False

    if title:
        query["title"] = {"$regex": title, "$options": "i"}
        filters_applied = True
    if author:
        query["author"] = {"$regex": author, "$options": "i"}
        filters_applied = True
    if keyword_input:
        keywords = [k.strip().lower() for k in keyword_input.split(",") if k.strip()]
        query["keywords"] = {"$in": keywords}
        filters_applied = True
    if language_filter != "All":
        query["language"] = language_filter
        filters_applied = True
    if course_filter != "All":
        query["course"] = course_filter
        filters_applied = True

    books = []
    if submitted:
        if filters_applied:
            books = list(books_col.find(query).sort("uploaded_at", -1).limit(50))
        else:
            books = list(books_col.find().sort("uploaded_at", -1).limit(3))

    missing_files = []
    ip = get_ip()
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    guest_downloads_today = logs_col.count_documents({
        "user": "guest",
        "ip": ip,
        "type": "download",
        "timestamp": {"$gte": today_start}
    })

    for book in books:
        with st.expander(book["title"]):
            st.write(f"**Author:** {book.get('author', 'N/A')}")
            st.write(f"**Language:** {book.get('language', 'N/A')}")
            st.write(f"**Course:** {book.get('course', 'Not tagged')}")
            st.write(f"**Keywords:** {', '.join(book.get('keywords', []))}")

            file_id = book.get("file_id")
            if not file_id:
                st.warning("⚠️ No file associated with this book.")
                missing_files.append(book["title"])
            else:
                try:
                    if not isinstance(file_id, ObjectId):
                        file_id = ObjectId(file_id)
                    grid_file = fs.get(file_id)
                    data = grid_file.read()
                    file_name = grid_file.filename

                    user = st.session_state.get("user")
                    can_download = user or guest_downloads_today < 1

                    if can_download:
                        if st.download_button(
                            label="📄 Download Book",
                            data=data,
                            file_name=file_name,
                            mime="application/pdf",
                            key=f"download_{safe_key(book['_id'])}"
                        ):
                            logs_col.insert_one({
                                "type": "download",
                                "user": user if user else "guest",
                                "ip": ip,
                                "book": book["title"],
                                "author": book.get("author"),
                                "language": book.get("language"),
                                "timestamp": datetime.utcnow()
                            })
                    else:
                        st.warning("Guests can download only 1 book per day. Please log in.")
                except Exception as e:
                    st.error(f"❌ Could not retrieve file: {e}")
                    missing_files.append(book["title"])

            # Bookmark button
            user = st.session_state.get("user")
            if user and st.button("⭐ Bookmark", key=f"bookmark_{safe_key(book['_id'])}"):
                fav_col.update_one(
                    {"user": user, "book_id": str(book['_id'])},
                    {"$set": {"timestamp": datetime.utcnow()}},
                    upsert=True
                )
                st.success("Bookmarked")

    if st.session_state.get("user") == "admin" and missing_files:
        st.error("⚠️ Missing files for:")
        for title in missing_files:
            st.write(f"- {title}")

# --- Manage Users ---
def manage_users():
    st.subheader("👥 Manage Users")

    search_query = st.text_input("Search by username", key="search_user")
    query = {"username": {"$regex": search_query, "$options": "i"}} if search_query else {}
    users = list(users_col.find(query))

    if not users:
        st.info("No users found.")
        return

    for user in users:
        with st.expander(f"👤 {user['username']}"):
            st.write(f"✅ Verified: {'Yes' if user.get("verified") else 'No'}")
            st.write(f"🕒 Joined: {user.get("created_at", 'N/A')}")

            dl_count = logs_col.count_documents({"user": user["username"], "type": "download"})
            fav_count = fav_col.count_documents({"user": user["username"]})
            st.write(f"📥 Downloads: {dl_count}")
            st.write(f"⭐ Bookmarks: {fav_count}")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("✅ Toggle Verified", key=f"verify_{safe_key(user['_id'])}"):
                    users_col.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"verified": not user.get("verified", False)}}
                    )
                    st.success("Updated")
                    rerun()

            with col2:
                if st.button("❌ Delete User", key=f"delete_{safe_key(user['_id'])}"):
                    if user["username"] == st.session_state.get("user"):
                        st.error("Can't delete yourself")
                    else:
                        if st.checkbox(f"Confirm delete {user['username']}?", key=f"confirm_{safe_key(user['_id'])}"):
                            users_col.delete_one({"_id": user["_id"]})
                            logs_col.delete_many({"user": user["username"]})
                            fav_col.delete_many({"user": user["username"]})
                            st.warning("User deleted")
                            rerun()

# --- Edit Metadata, Add Course, Bulk Upload, Clear Collections ---
# Keep same as before: they already use st.experimental_rerun

# --- Main ---
def main():
    st.set_page_config("📚 DS Book Library")
    st.title("📚 DataScience E-Book Library")

    search_books()
    st.markdown("---")

    if "user" not in st.session_state:
        with st.sidebar:
            choice = st.radio("Choose:", ["Login", "Register"])
            if choice == "Login":
                login_user()
            else:
                register_user()
        st.stop()

    user = st.session_state["user"]
    st.success(f"Logged in as: {user}")

    if user == "admin":
        st.sidebar.markdown("## 🔐 Admin Controls")
        admin_tab = st.sidebar.radio("🛠️ Admin Panel", [
            "📤 Upload Book",
            "📥 Bulk Upload",
            "📊 Analytics",
            "👥 Manage Users",
            "📝 Edit Book Metadata",
            "➕ Add Course",
            "⚠️ Clear Collections"
        ])

        if admin_tab == "📤 Upload Book":
            upload_book()
        elif admin_tab == "📥 Bulk Upload":
            bulk_upload_with_gridfs()
        elif admin_tab == "📊 Analytics":
            admin_dashboard()
        elif admin_tab == "👥 Manage Users":
            manage_users()
        elif admin_tab == "📝 Edit Book Metadata":
            edit_book_metadata()
        elif admin_tab == "➕ Add Course":
            add_new_course()
        elif admin_tab == "⚠️ Clear Collections":
            clear_collections()
        else:
            user_dashboard(user)
    else:
        user_dashboard(user)

    if st.button("Logout"):
        st.session_state.clear()
        rerun()

if __name__ == "__main__":
    main()
