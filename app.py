import os
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(
    page_title="Daily Work Tracker",
    page_icon="📘",
    layout="wide"
)

st.title("📘 Daily Work & Achievement Tracker")
st.caption("Projects • PPTs • LinkedIn • GitHub • Learning")

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
    sql = """
        SELECT * FROM work_entries
        WHERE (:category IS NULL OR category = :category)
          AND (
              :search = ''
              OR LOWER(title || ' ' || COALESCE(description, '')
                  || ' ' || COALESCE(skills, ''))
                  LIKE :pattern
          )
        ORDER BY work_date DESC, id DESC
    """

    with engine.connect() as conn:
        result = conn.execute(text(sql), {
            "category": category,
            "search": search.lower().strip(),
            "pattern": f"%{search.lower().strip()}%"
        })

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
    st.header("📘 My Tracker")

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
