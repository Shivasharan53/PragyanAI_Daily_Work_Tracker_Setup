import os
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

st.set_page_config(
    page_title="Daily Work Tracker",
    page_icon="📘",
    layout="wide"
)

st.markdown("""
<style>
.stApp { background:linear-gradient(180deg,#071525 0%,#091a2b 48%,#061321 100%); color:#f4f7ff; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#061321 0%,#0a1c2e 100%); border-right:1px solid rgba(148,163,184,.18); }
[data-testid="stSidebar"] * { color:#edf4ff; }
.block-container { padding-top:1.25rem; max-width:1500px; }
.hero { min-height:250px; padding:28px 30px; margin-bottom:20px; border-radius:22px; overflow:hidden;
 border:1px solid rgba(255,255,255,.18);
 background:linear-gradient(90deg,rgba(3,12,27,.92) 0%,rgba(4,17,35,.62) 55%,rgba(4,14,28,.12) 100%),
 linear-gradient(0deg,rgba(3,12,27,.62),rgba(3,12,27,.04)),
 url("https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1800&q=85");
 background-size:cover; background-position:center 48%; box-shadow:0 18px 55px rgba(0,0,0,.28); }
.hero-kicker { display:inline-block; padding:7px 12px; border-radius:999px; background:rgba(124,58,237,.3); border:1px solid rgba(196,181,253,.4); color:#f5d0fe; font-size:12px; }
.hero h1 { color:#fff; font-size:clamp(28px,3.3vw,46px); line-height:1.1; margin:18px 0 12px; font-weight:850; }
.hero .subtitle { color:#e2eaff; font-size:15px; }
.hero .quote { margin-top:18px; color:#fff; font-size:18px; font-style:italic; }
.hero .welcome { text-align:right; color:#f8fafc; font-size:13px; }
div[data-testid="stMetric"] { background:linear-gradient(145deg,rgba(15,31,51,.96),rgba(7,20,35,.96)); border:1px solid rgba(148,163,184,.25); padding:16px 17px; border-radius:16px; box-shadow:0 10px 28px rgba(0,0,0,.16); }
div[data-testid="stMetricLabel"] { color:#bcd0e7; } div[data-testid="stMetricValue"] { color:#fff; }
div[data-testid="stVerticalBlockBorderWrapper"] { background:rgba(8,23,39,.82); border-color:rgba(148,163,184,.23); border-radius:16px; }
.stButton > button, div[data-testid="stFormSubmitButton"] > button { border-radius:11px; border:1px solid rgba(196,181,253,.32); background:linear-gradient(100deg,#2563eb,#7c3aed); color:white; font-weight:650; }
h1,h2,h3 { color:#f8fafc; } [data-testid="stCaptionContainer"] { color:#a9bdd6; }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="hero">
  <div class="welcome">🌅 Personal portfolio · {date.today().strftime("%A, %d %b %Y")}</div>
  <span class="hero-kicker">Projects&nbsp; • &nbsp;PPTs&nbsp; • &nbsp;LinkedIn&nbsp; • &nbsp;GitHub&nbsp; • &nbsp;Learning</span>
  <h1>Daily Work &amp; Achievement Tracker</h1>
  <div class="subtitle">Track your work. Celebrate your progress. Build your future.</div>
  <div class="quote">“A better version of myself, every day.”</div>
</div>
""", unsafe_allow_html=True)

# ---------- CONFIGURATION ----------

def setting(key):
    try:
        return st.secrets.get(key, os.getenv(key, ""))
    except Exception:
        return os.getenv(key, "")

APP_PASSWORD = setting("APP_PASSWORD")
DATABASE_URL = setting("DATABASE_URL")

if not APP_PASSWORD or not DATABASE_URL:
    st.error("Configure APP_PASSWORD and DATABASE_URL in Streamlit Secrets.")
    st.stop()

if not st.session_state.get("logged_in"):
    st.subheader("🔐 Personal Login")

    with st.form("login"):
        password = st.text_input("Enter app password", type="password")
        submit = st.form_submit_button("Login")

    if submit:
        if password == APP_PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

@st.cache_resource
def get_engine(url):
    return create_engine(url, pool_pre_ping=True)

engine = get_engine(DATABASE_URL)

with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS work_entries (
            id BIGSERIAL PRIMARY KEY,
            work_date DATE NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            outcome TEXT DEFAULT '',
            skills TEXT DEFAULT '',
            hours NUMERIC(6,2),
            status TEXT DEFAULT 'Completed',
            github_url TEXT DEFAULT '',
            demo_url TEXT DEFAULT '',
            ppt_url TEXT DEFAULT '',
            linkedin_url TEXT DEFAULT '',
            next_step TEXT DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

CATEGORIES = [
    "Daily Work", "Project", "PPT",
    "LinkedIn Post", "GitHub Update",
    "Learning", "Job Search", "Other"
]

STATUSES = [
    "Completed", "In Progress", "Draft",
    "Published", "Blocked", "To Do"
]


def get_data(category=None, search=""):
    conditions = []
    params = {}

    if category is not None:
        conditions.append("category = :category")
        params["category"] = category

    search_term = search.lower().strip()
    if search_term:
        conditions.append("""
            LOWER(title || ' ' || COALESCE(description, '')
                || ' ' || COALESCE(skills, '')) LIKE :pattern
        """)
        params["pattern"] = f"%{search_term}%"

    sql = "SELECT * FROM work_entries"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY work_date DESC, id DESC"

    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        return pd.DataFrame(result.mappings().all())


def save_entry(values, entry_id=None):
    if entry_id is None:
        sql = """
            INSERT INTO work_entries (
                work_date, category, title, description,
                outcome, skills, hours, status,
                github_url, demo_url, ppt_url,
                linkedin_url, next_step
            )
            VALUES (
                :work_date, :category, :title, :description,
                :outcome, :skills, :hours, :status,
                :github_url, :demo_url, :ppt_url,
                :linkedin_url, :next_step
            )
        """
    else:
        sql = """
            UPDATE work_entries SET
                work_date=:work_date,
                category=:category,
                title=:title,
                description=:description,
                outcome=:outcome,
                skills=:skills,
                hours=:hours,
                status=:status,
                github_url=:github_url,
                demo_url=:demo_url,
                ppt_url=:ppt_url,
                linkedin_url=:linkedin_url,
                next_step=:next_step
            WHERE id=:id
        """
        values["id"] = int(entry_id)

    with engine.begin() as conn:
        conn.execute(text(sql), values)


def delete_entry(entry_id):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM work_entries WHERE id=:id"),
            {"id": int(entry_id)}
        )


def show_link(label, url):
    if url and url.startswith(("https://", "http://")):
        st.markdown(f"[{label} ↗]({url})")


# ---------- SIDEBAR ----------

with st.sidebar:
    st.markdown("### 🟪 Daily Work Tracker")
    st.caption("Consistency today, success tomorrow.")
    st.header("📘 My Tracker")
    if is_owner:
        st.success("Owner mode · Full access")
        if st.button("🔒 Log out"):
            st.session_state.logged_in = False
            st.session_state.pop("user_role", None)
            st.rerun()
    else:
        st.info("🌐 Public View · Read-only")
        with st.expander("Owner login"):
            with st.form("owner_login"):
                owner_password = st.text_input("Owner password", type="password")
                owner_submit = st.form_submit_button("Log in")
            if owner_submit:
                if owner_password == APP_PASSWORD:
                    st.session_state.logged_in = True
                    st.session_state.user_role = "owner"
                    st.rerun()
                else:
                    st.error("Incorrect owner password.")


    page = st.radio("Navigation", [
        "Dashboard",
        "Daily Work",
        "Projects",
        "PPT Tracker",
        "LinkedIn Posts",
        "GitHub Updates",
        "Learning",
        "Backup"
    ])

    if st.button("🔒 Logout"):
        st.session_state.logged_in = False
        st.rerun()


# ---------- DASHBOARD ----------

if page == "Dashboard":
    df = get_data()

    today_count = (
        len(df[df["work_date"].astype(str) == str(date.today())])
        if not df.empty else 0
    )

    month_count = (
        len(df[df["work_date"].astype(str).str.startswith(
            date.today().strftime("%Y-%m")
        )])
        if not df.empty else 0
    )

    a, b, c, d = st.columns(4)

    a.metric("Total Entries", len(df))
    b.metric("Today's Entries", today_count)
    c.metric("This Month", month_count)

    link_count = 0
    if not df.empty:
        for col in [
            "github_url", "demo_url",
            "ppt_url", "linkedin_url"
        ]:
            link_count += df[col].fillna("").astype(str).str.startswith(
                ("https://", "http://")
            ).sum()

    d.metric("Links Saved", int(link_count))

    if is_owner:
        st.subheader("⚡ Quick Add")

        with st.expander("➕ Record Today's Work", expanded=True):
            with st.form("quick_add"):
                work_date = st.date_input("Date", date.today())
                category = st.selectbox("Category", CATEGORIES)
                title = st.text_input("Work title *")
                description = st.text_area("Tasks / notes")
                outcome = st.text_area("Achievement / result")
                skills = st.text_input("Tools / skills")
                hours = st.number_input(
                    "Hours spent", min_value=0.0, max_value=24.0, step=0.5
                )
                status = st.selectbox("Status", STATUSES)

                github_url = st.text_input("GitHub URL")
                demo_url = st.text_input("Live project URL")
                ppt_url = st.text_input("PPT / document URL")
                linkedin_url = st.text_input("LinkedIn post URL")
                next_step = st.text_input("Tomorrow's priority")

                submitted = st.form_submit_button(
                    "💾 Save Entry",
                    type="primary"
                )

            if submitted:
                if not title.strip():
                    st.error("Enter a title.")
                else:
                    links = [
                        github_url, demo_url, ppt_url, linkedin_url
                    ]

                    if any(
                        u.strip() and not u.strip().startswith(
                            ("https://", "http://")
                        )
                        for u in links
                    ):
                        st.error("Links must start with https:// or http://")
                    else:
                        save_entry({
                            "work_date": work_date,
                            "category": category,
                            "title": title.strip(),
                            "description": description,
                            "outcome": outcome,
                            "skills": skills,
                            "hours": hours if hours > 0 else None,
                            "status": status,
                            "github_url": github_url.strip(),
                            "demo_url": demo_url.strip(),
                            "ppt_url": ppt_url.strip(),
                            "linkedin_url": linkedin_url.strip(),
                            "next_step": next_step
                        })

                        st.success("Entry saved!")
                        st.rerun()

    st.subheader("🕒 Recent Activity")

    if df.empty:
        st.info("Your tracker is empty. Add your first entry above.")
    else:
        for _, row in df.head(5).iterrows():
            with st.container(border=True):
                st.markdown(f"### {row['title']}")
                st.caption(
                    f"{row['work_date']} • "
                    f"{row['category']} • {row['status']}"
                )
                st.write(row["description"] or "")
                st.write(row["outcome"] or "")

                show_link("GitHub", row["github_url"])
                show_link("Live Project", row["demo_url"])
                show_link("PPT", row["ppt_url"])
                show_link("LinkedIn Post", row["linkedin_url"])


# ---------- CATEGORY PAGES ----------

elif page in [
    "Daily Work", "Projects", "PPT Tracker",
    "LinkedIn Posts", "GitHub Updates", "Learning"
]:
    category_map = {
        "Daily Work": "Daily Work",
        "Projects": "Project",
        "PPT Tracker": "PPT",
        "LinkedIn Posts": "LinkedIn Post",
        "GitHub Updates": "GitHub Update",
        "Learning": "Learning"
    }

    category = category_map[page]
    st.subheader(page)

    search = st.text_input("🔎 Search entries")
    df = get_data(category, search)

    if df.empty:
        st.info("No entries found.")
    else:
        for _, row in df.iterrows():
            with st.container(border=True):
                st.markdown(f"### {row['title']}")
                st.caption(
                    f"{row['work_date']} • {row['status']}"
                )

                st.write(row["description"] or "")
                st.write("**Achievement:** " + (row["outcome"] or ""))
                st.write("**Skills:** " + (row["skills"] or ""))

                show_link("GitHub", row["github_url"])
                show_link("Live Project", row["demo_url"])
                show_link("PPT", row["ppt_url"])
                show_link("LinkedIn", row["linkedin_url"])

                if is_owner:
                    with st.expander("✏️ Edit or delete"):
                        with st.form(f"edit_{row['id']}"):
                            title = st.text_input(
                                "Title", value=row["title"]
                            )
                            description = st.text_area(
                                "Notes", value=row["description"] or ""
                            )
                            outcome = st.text_area(
                                "Achievement", value=row["outcome"] or ""
                            )
                            skills = st.text_input(
                                "Skills", value=row["skills"] or ""
                            )
                            status = st.selectbox(
                                "Status", STATUSES,
                                index=(
                                    STATUSES.index(row["status"])
                                    if row["status"] in STATUSES else 0
                                )
                            )
                            next_step = st.text_input(
                                "Next step", value=row["next_step"] or ""
                            )

                            update = st.form_submit_button("Save Changes")

                        if update:
                            with engine.begin() as conn:
                                conn.execute(text("""
                                    UPDATE work_entries SET
                                    title=:title,
                                    description=:description,
                                    outcome=:outcome,
                                    skills=:skills,
                                    status=:status,
                                    next_step=:next_step
                                    WHERE id=:id
                                """), {
                                    "id": int(row["id"]),
                                    "title": title,
                                    "description": description,
                                    "outcome": outcome,
                                    "skills": skills,
                                    "status": status,
                                    "next_step": next_step
                                })

                            st.success("Updated!")
                            st.rerun()

                        if st.button(
                            "🗑️ Delete Entry",
                            key=f"delete_{row['id']}"
                        ):
                            delete_entry(row["id"])
                            st.rerun()


# ---------- BACKUP ----------

elif page == "Backup":
    st.subheader("💾 Export Your Records")

    df = get_data()

    if df.empty:
        st.info("No entries to export yet.")
    else:
        st.download_button(
            "⬇️ Download CSV Backup",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name="daily_work_tracker.csv",
            mime="text/csv"
        )

        st.download_button(
            "⬇️ Download JSON Backup",
            df.to_json(orient="records", indent=2).encode("utf-8"),
            file_name="daily_work_tracker.json",
            mime="application/json"
        )

        st.dataframe(df, use_container_width=True, hide_index=True)

    st.warning(
        "Keep your database URL and app password private. "
        "Export backups regularly."
    )

st.divider()
st.caption("Your work. Your progress. One place.")
