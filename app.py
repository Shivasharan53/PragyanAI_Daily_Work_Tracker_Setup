import os
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Daily Work Tracker",
    page_icon="📘",
    layout="wide",
)


# =========================================================
# STYLING
# =========================================================

st.markdown("""
<style>
.stApp {
    background: linear-gradient(
        180deg, #071525 0%, #091a2b 48%, #061321 100%
    );
    color: #f4f7ff;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #061321 0%, #0a1c2e 100%);
    border-right: 1px solid rgba(148,163,184,.18);
}
[data-testid="stSidebar"] * { color: #edf4ff; }
.block-container {
    padding-top: 1.25rem;
    max-width: 1500px;
}
.hero {
    min-height: 250px;
    padding: 28px 30px;
    margin-bottom: 20px;
    border-radius: 22px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,.18);
    background:
        linear-gradient(
            90deg,
            rgba(3,12,27,.92) 0%,
            rgba(4,17,35,.62) 55%,
            rgba(4,14,28,.12) 100%
        ),
        linear-gradient(
            0deg,
            rgba(3,12,27,.62),
            rgba(3,12,27,.04)
        ),
        url("https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1800&q=85");
    background-size: cover;
    background-position: center 48%;
    box-shadow: 0 18px 55px rgba(0,0,0,.28);
}
.hero-kicker {
    display: inline-block;
    padding: 7px 12px;
    border-radius: 999px;
    background: rgba(124,58,237,.3);
    border: 1px solid rgba(196,181,253,.4);
    color: #f5d0fe;
    font-size: 12px;
}
.hero h1 {
    color: #fff;
    font-size: clamp(28px,3.3vw,46px);
    line-height: 1.1;
    margin: 18px 0 12px;
    font-weight: 850;
}
.hero .subtitle {
    color: #e2eaff;
    font-size: 15px;
}
.hero .quote {
    margin-top: 18px;
    color: #fff;
    font-size: 18px;
    font-style: italic;
}
.hero .welcome {
    text-align: right;
    color: #f8fafc;
    font-size: 13px;
}
div[data-testid="stMetric"] {
    background: linear-gradient(
        145deg, rgba(15,31,51,.96), rgba(7,20,35,.96)
    );
    border: 1px solid rgba(148,163,184,.25);
    padding: 16px 17px;
    border-radius: 16px;
    box-shadow: 0 10px 28px rgba(0,0,0,.16);
}
div[data-testid="stMetricLabel"] { color: #bcd0e7; }
div[data-testid="stMetricValue"] { color: #fff; }
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(8,23,39,.82);
    border-color: rgba(148,163,184,.23);
    border-radius: 16px;
}
.stButton > button,
div[data-testid="stFormSubmitButton"] > button {
    border-radius: 11px;
    border: 1px solid rgba(196,181,253,.32);
    background: linear-gradient(100deg,#2563eb,#7c3aed);
    color: white;
    font-weight: 650;
}
h1, h2, h3 { color: #f8fafc; }
[data-testid="stCaptionContainer"] { color: #a9bdd6; }
</style>
""", unsafe_allow_html=True)


# =========================================================
# SETTINGS AND DATABASE CONNECTION
# =========================================================

def setting(key):
    try:
        return st.secrets.get(key, os.getenv(key, ""))
    except Exception:
        return os.getenv(key, "")


APP_PASSWORD = setting("APP_PASSWORD")
DATABASE_URL = setting("DATABASE_URL")

if not APP_PASSWORD or not DATABASE_URL:
    st.error(
        "Configure APP_PASSWORD and DATABASE_URL "
        "in your Streamlit app Secrets."
    )
    st.stop()


# Support PostgreSQL connection URL formats.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]

elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = (
        "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]
    )


@st.cache_resource
def get_engine(url):
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


try:
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

except Exception as exc:
    st.error("Could not connect to the database. Check DATABASE_URL.")
    st.exception(exc)
    st.stop()


# =========================================================
# CONSTANTS
# =========================================================

CATEGORIES = [
    "Daily Work",
    "Project",
    "PPT",
    "LinkedIn Post",
    "GitHub Update",
    "Learning",
    "Job Search",
    "Other",
]

STATUSES = [
    "Completed",
    "In Progress",
    "Draft",
    "Published",
    "Blocked",
    "To Do",
]


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def get_data(category=None, search=""):
    conditions = []
    params = {}

    if category:
        conditions.append("category = :category")
        params["category"] = category

    search_term = search.strip().lower()

    if search_term:
        conditions.append("""
            LOWER(
                COALESCE(title, '') || ' ' ||
                COALESCE(description, '') || ' ' ||
                COALESCE(outcome, '') || ' ' ||
                COALESCE(skills, '')
            ) LIKE :pattern
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
                work_date = :work_date,
                category = :category,
                title = :title,
                description = :description,
                outcome = :outcome,
                skills = :skills,
                hours = :hours,
                status = :status,
                github_url = :github_url,
                demo_url = :demo_url,
                ppt_url = :ppt_url,
                linkedin_url = :linkedin_url,
                next_step = :next_step
            WHERE id = :id
        """
        values["id"] = int(entry_id)

    with engine.begin() as conn:
        conn.execute(text(sql), values)


def delete_entry(entry_id):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM work_entries WHERE id = :id"),
            {"id": int(entry_id)},
        )


# =========================================================
# DISPLAY HELPERS
# =========================================================

def show_link(label, url):
    if isinstance(url, str) and url.strip().startswith(
        ("https://", "http://")
    ):
        st.markdown(f"[{label} ↗]({url.strip()})")


def display_entry(row, allow_edit=False):
    with st.container(border=True):
        st.markdown(f"### {row['title']}")

        st.caption(
            f"{row['work_date']}  •  "
            f"{row['category']}  •  {row['status']}"
        )

        if row.get("description"):
            st.write(row["description"])

        if row.get("outcome"):
            st.write(f"**Achievement:** {row['outcome']}")

        if row.get("skills"):
            st.write(f"**Skills / Tools:** {row['skills']}")

        if row.get("hours") is not None and pd.notna(row.get("hours")):
            st.write(f"**Hours spent:** {row['hours']}")

        show_link("GitHub", row.get("github_url"))
        show_link("Live Project", row.get("demo_url"))
        show_link("PPT / Document", row.get("ppt_url"))
        show_link("LinkedIn Post", row.get("linkedin_url"))

        if row.get("next_step"):
            st.write(f"**Next step:** {row['next_step']}")

        if allow_edit:
            with st.expander("✏️ Edit or delete this entry"):
                date_value = row["work_date"]

                if isinstance(date_value, str):
                    date_value = date.fromisoformat(date_value[:10])
                elif hasattr(date_value, "date"):
                    date_value = date_value.date()

                with st.form(f"edit_form_{row['id']}"):
                    edit_date = st.date_input(
                        "Date",
                        value=date_value,
                        key=f"date_{row['id']}",
                    )

                    edit_category = st.selectbox(
                        "Category",
                        CATEGORIES,
                        index=(
                            CATEGORIES.index(row["category"])
                            if row["category"] in CATEGORIES else 0
                        ),
                        key=f"category_{row['id']}",
                    )

                    edit_title = st.text_input(
                        "Work title",
                        value=row["title"] or "",
                        key=f"title_{row['id']}",
                    )

                    edit_description = st.text_area(
                        "Tasks / notes",
                        value=row["description"] or "",
                        key=f"description_{row['id']}",
                    )

                    edit_outcome = st.text_area(
                        "Achievement / result",
                        value=row["outcome"] or "",
                        key=f"outcome_{row['id']}",
                    )

                    edit_skills = st.text_input(
                        "Tools / skills",
                        value=row["skills"] or "",
                        key=f"skills_{row['id']}",
                    )

                    current_hours = row.get("hours")
                    if current_hours is None or pd.isna(current_hours):
                        current_hours = 0.0

                    edit_hours = st.number_input(
                        "Hours spent",
                        min_value=0.0,
                        max_value=24.0,
                        step=0.5,
                        value=float(current_hours),
                        key=f"hours_{row['id']}",
                    )

                    edit_status = st.selectbox(
                        "Status",
                        STATUSES,
                        index=(
                            STATUSES.index(row["status"])
                            if row["status"] in STATUSES else 0
                        ),
                        key=f"status_{row['id']}",
                    )

                    edit_github = st.text_input(
                        "GitHub URL",
                        value=row["github_url"] or "",
                        key=f"github_{row['id']}",
                    )

                    edit_demo = st.text_input(
                        "Live project URL",
                        value=row["demo_url"] or "",
                        key=f"demo_{row['id']}",
                    )

                    edit_ppt = st.text_input(
                        "PPT / document URL",
                        value=row["ppt_url"] or "",
                        key=f"ppt_{row['id']}",
                    )

                    edit_linkedin = st.text_input(
                        "LinkedIn post URL",
                        value=row["linkedin_url"] or "",
                        key=f"linkedin_{row['id']}",
                    )

                    edit_next_step = st.text_input(
                        "Next priority",
                        value=row["next_step"] or "",
                        key=f"next_{row['id']}",
                    )

                    update = st.form_submit_button("💾 Save Changes")

                if update:
                    if not edit_title.strip():
                        st.error("Please enter a work title.")
                    else:
                        links = [
                            edit_github,
                            edit_demo,
                            edit_ppt,
                            edit_linkedin,
                        ]

                        invalid_links = [
                            link.strip()
                            for link in links
                            if link.strip()
                            and not link.strip().startswith(
                                ("https://", "http://")
                            )
                        ]

                        if invalid_links:
                            st.error(
                                "Every link must start with "
                                "https:// or http://"
                            )
                        else:
                            save_entry(
                                {
                                    "work_date": edit_date,
                                    "category": edit_category,
                                    "title": edit_title.strip(),
                                    "description": edit_description,
                                    "outcome": edit_outcome,
                                    "skills": edit_skills,
                                    "hours": edit_hours if edit_hours > 0 else None,
                                    "status": edit_status,
                                    "github_url": edit_github.strip(),
                                    "demo_url": edit_demo.strip(),
                                    "ppt_url": edit_ppt.strip(),
                                    "linkedin_url": edit_linkedin.strip(),
                                    "next_step": edit_next_step,
                                },
                                entry_id=row["id"],
                            )

                            st.success("Entry updated successfully!")
                            st.rerun()

                confirm_delete = st.checkbox(
                    "I want to delete this entry",
                    key=f"confirm_delete_{row['id']}",
                )

                if st.button(
                    "🗑️ Delete Entry",
                    key=f"delete_{row['id']}",
                    disabled=not confirm_delete,
                ):
                    delete_entry(row["id"])
                    st.success("Entry deleted.")
                    st.rerun()


# =========================================================
# OWNER LOGIN AND NAVIGATION
# =========================================================

if "user_role" not in st.session_state:
    st.session_state.user_role = "public"

with st.sidebar:
    st.markdown("### 🟪 Daily Work Tracker")
    st.caption("A better version of myself, every day.")
    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Home",
            "Dashboard",
            "About",
            "My Work",
            "Daily Work",
            "Projects",
            "PPT Tracker",
            "LinkedIn Posts",
            "GitHub Updates",
            "Learning",
            "Backup",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    if st.session_state.get("user_role") == "owner":
        st.success("🔓 Owner mode · Full access")

        if st.button("🔒 Log out", use_container_width=True):
            st.session_state.user_role = "public"
            st.session_state.pop("logged_in", None)
            st.rerun()

    else:
        st.caption("🌐 Public view · Read-only")

        with st.expander("🔐 Owner login"):
            with st.form("owner_login_form"):
                owner_password = st.text_input(
                    "Owner password",
                    type="password",
                )
                owner
