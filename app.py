import os
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Daily Work Tracker",
    page_icon="📘",
    layout="wide",
)


# =========================================================
# 2. DARK THEME + SCENIC HERO
# =========================================================

st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #071525 0%, #091a2b 48%, #061321 100%);
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
# 3. APP SETTINGS
# =========================================================

def get_setting(key):
    try:
        value = st.secrets.get(key, "")
        if value:
            return str(value)
    except Exception:
        pass

    return os.getenv(key, "")


APP_PASSWORD = get_setting("APP_PASSWORD")
DATABASE_URL = get_setting("DATABASE_URL")

if not APP_PASSWORD or not DATABASE_URL:
    st.error(
        "Missing configuration. Add APP_PASSWORD and DATABASE_URL "
        "in Streamlit app Secrets."
    )
    st.stop()


# Convert PostgreSQL URL to the psycopg SQLAlchemy driver.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = (
        "postgresql+psycopg://"
        + DATABASE_URL[len("postgres://"):]
    )
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = (
        "postgresql+psycopg://"
        + DATABASE_URL[len("postgresql://"):]
    )


@st.cache_resource
def get_engine(database_url):
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


try:
    engine = get_engine(DATABASE_URL)

    # Create the table if it does not already exist.
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

except Exception:
    st.error(
        "Database connection failed. Check your existing "
        "DATABASE_URL and the Streamlit app logs."
    )
    st.stop()


# =========================================================
# 4. CONSTANTS
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

ENTRY_FIELDS = [
    "work_date",
    "category",
    "title",
    "description",
    "outcome",
    "skills",
    "hours",
    "status",
    "github_url",
    "demo_url",
    "ppt_url",
    "linkedin_url",
    "next_step",
]


# =========================================================
# 5. DATABASE READ FUNCTION
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


# =========================================================
# 6. DATABASE INSERT / UPDATE FUNCTION
# =========================================================

def save_entry(values, entry_id=None):
    """
    Insert or update an entry.
    Build the parameters explicitly so SQL placeholders
    and supplied values always match.
    """

    data = {
        field: values.get(field)
        for field in ENTRY_FIELDS
    }

    # Normalize optional text fields.
    text_fields = [
        "description",
        "outcome",
        "skills",
        "github_url",
        "demo_url",
        "ppt_url",
        "linkedin_url",
        "next_step",
    ]

    for field in text_fields:
        data[field] = data[field] or ""

    data["title"] = (data["title"] or "").strip()

    if not data["title"]:
        raise ValueError("Work title cannot be empty.")

    if data["category"] not in CATEGORIES:
        raise ValueError("Invalid category.")

    if data["status"] not in STATUSES:
        raise ValueError("Invalid status.")

    # Use separate SQL statements for inserts and updates.
    if entry_id is None:
        sql = text("""
            INSERT INTO work_entries (
                work_date,
                category,
                title,
                description,
                outcome,
                skills,
                hours,
                status,
                github_url,
                demo_url,
                ppt_url,
                linkedin_url,
                next_step
            )
            VALUES (
                :work_date,
                :category,
                :title,
                :description,
                :outcome,
                :skills,
                :hours,
                :status,
                :github_url,
                :demo_url,
                :ppt_url,
                :linkedin_url,
                :next_step
            )
        """)

    else:
        data["id"] = int(entry_id)

        sql = text("""
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
        """)

    with engine.begin() as conn:
        conn.execute(sql, data)


# =========================================================
# 7. DATABASE DELETE FUNCTION
# =========================================================

def delete_entry(entry_id):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM work_entries WHERE id = :id"),
            {"id": int(entry_id)},
        )


# =========================================================
# 8. LINK DISPLAY HELPER
# =========================================================

def show_link(label, url):
    if isinstance(url, str):
        clean_url = url.strip()

        if clean_url.startswith(("https://", "http://")):
            st.markdown(f"[{label} ↗]({clean_url})")


# =========================================================
# 9. ENTRY DISPLAY AND OWNER EDITING
# =========================================================

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

        hours_value = row.get("hours")
        if hours_value is not None and pd.notna(hours_value):
            st.write(f"**Hours spent:** {hours_value}")

        show_link("GitHub", row.get("github_url"))
        show_link("Live Project", row.get("demo_url"))
        show_link("PPT / Document", row.get("ppt_url"))
        show_link("LinkedIn Post", row.get("linkedin_url"))

        if row.get("next_step"):
            st.write(f"**Next step:** {row['next_step']}")

        if not allow_edit:
            return

        entry_id = int(row["id"])

        with st.expander("✏️ Edit or delete this entry"):
            entry_date = row["work_date"]

            if isinstance(entry_date, str):
                entry_date = date.fromisoformat(entry_date[:10])
            elif hasattr(entry_date, "date"):
                entry_date = entry_date.date()

            current_category = row["category"]
            if current_category not in CATEGORIES:
                current_category = "Other"

            current_status = row["status"]
            if current_status not in STATUSES:
                current_status = "Completed"

            current_hours = row.get("hours")
            if current_hours is None or pd.isna(current_hours):
                current_hours = 0.0

            with st.form(f"edit_form_{entry_id}"):
                edit_date = st.date_input(
                    "Date",
                    value=entry_date,
                    key=f"edit_date_{entry_id}",
                )

                edit_category = st.selectbox(
                    "Category",
                    CATEGORIES,
                    index=CATEGORIES.index(current_category),
                    key=f"edit_category_{entry_id}",
                )

                edit_title = st.text_input(
                    "Work title *",
                    value=row["title"] or "",
                    key=f"edit_title_{entry_id}",
                )

                edit_description = st.text_area(
                    "Tasks / notes",
                    value=row["description"] or "",
                    key=f"edit_description_{entry_id}",
                )

                edit_outcome = st.text_area(
                    "Achievement / result",
                    value=row["outcome"] or "",
                    key=f"edit_outcome_{entry_id}",
                )

                edit_skills = st.text_input(
                    "Tools / skills",
                    value=row["skills"] or "",
                    key=f"edit_skills_{entry_id}",
                )

                edit_hours = st.number_input(
                    "Hours spent",
                    min_value=0.0,
                    max_value=24.0,
                    value=float(current_hours),
                    step=0.5,
                    key=f"edit_hours_{entry_id}",
                )

                edit_status = st.selectbox(
                    "Status",
                    STATUSES,
                    index=STATUSES.index(current_status),
                    key=f"edit_status_{entry_id}",
                )

                edit_github = st.text_input(
                    "GitHub URL",
                    value=row["github_url"] or "",
                    key=f"edit_github_{entry_id}",
                )

                edit_demo = st.text_input(
                    "Live project URL",
                    value=row["demo_url"] or "",
                    key=f"edit_demo_{entry_id}",
                )

                edit_ppt = st.text_input(
                    "PPT / document URL",
                    value=row["ppt_url"] or "",
                    key=f"edit_ppt_{entry_id}",
                )

                edit_linkedin = st.text_input(
                    "LinkedIn post URL",
                    value=row["linkedin_url"] or "",
                    key=f"edit_linkedin_{entry_id}",
                )

                edit_next_step = st.text_input(
                    "Next priority",
                    value=row["next_step"] or "",
                    key=f"edit_next_step_{entry_id}",
                )

                update_clicked = st.form_submit_button(
                    "💾 Save Changes",
                    type="primary",
                )

            if update_clicked:
                if not edit_title.strip():
                    st.error("Please enter a work title.")
                else:
                    edit_links = [
                        edit_github,
                        edit_demo,
                        edit_ppt,
                        edit_linkedin,
                    ]

                    invalid_links = [
                        link.strip()
                        for link in edit_links
                        if link.strip()
                        and not link.strip().startswith(
                            ("https://", "http://")
                        )
                    ]

                    if invalid_links:
                        st.error(
                            "Links must start with https:// or http://"
                        )
                    else:
                        try:
                            save_entry(
                                {
                                    "work_date": edit_date,
                                    "category": edit_category,
                                    "title": edit_title,
                                    "description": edit_description,
                                    "outcome": edit_outcome,
                                    "skills": edit_skills,
                                    "hours": (
                                        edit_hours if edit_hours > 0 else None
                                    ),
                                    "status": edit_status,
                                    "github_url": edit_github.strip(),
                                    "demo_url": edit_demo.strip(),
                                    "ppt_url": edit_ppt.strip(),
                                    "linkedin_url": edit_linkedin.strip(),
                                    "next_step": edit_next_step,
                                },
                                entry_id=entry_id,
                            )

                            st.success("Entry updated successfully!")
                            st.rerun()

                        except Exception:
                            st.error(
                                "Could not update this entry. "
                                "Check the Streamlit app logs."
                            )

            st.divider()
            st.warning("Deleting an entry cannot be undone.")

            confirm_delete = st.checkbox(
                "Confirm that I want to delete this entry",
                key=f"confirm_delete_{entry_id}",
            )

            if st.button(
                "🗑️ Delete Entry",
                key=f"delete_entry_{entry_id}",
                disabled=not confirm_delete,
            ):
                try:
                    delete_entry(entry_id)
                    st.success("Entry deleted.")
                    st.rerun()
                except Exception:
                    st.error(
                        "Could not delete the entry. "
                        "Check the Streamlit app logs."
                    )


# =========================================================
# 10. OWNER LOGIN + SIDEBAR NAVIGATION
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

                login_clicked = st.form_submit_button("Log in")

            if login_clicked:
                if owner_password == APP_PASSWORD:
                    st.session_state.user_role = "owner"
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Incorrect owner password.")

# Recalculate after login handling.
is_owner = st.session_state.get("user_role") == "owner"


# =========================================================
# 11. GLOBAL HERO
# =========================================================

st.markdown(f"""
<div class="hero">
    <div class="welcome">
        🌅 Personal portfolio · {date.today().strftime("%A, %d %b %Y")}
    </div>
    <span class="hero-kicker">
        Projects&nbsp; • &nbsp;PPTs&nbsp; • &nbsp;LinkedIn&nbsp; • &nbsp;GitHub&nbsp; • &nbsp;Learning
    </span>
    <h1>Daily Work &amp; Achievement Tracker</h1>
    <div class="subtitle">
        Track your work. Celebrate your progress. Build your future.
    </div>
    <div class="quote">“A better version of myself, every day.”</div>
</div>
""", unsafe_allow_html=True)


# =========================================================
# 12. HOME
# =========================================================

if page == "Home":
    st.subheader("Welcome to my work portfolio")

    st.write(
        "Explore daily activities, projects, presentations, learning, "
        "GitHub updates, and achievements."
    )

    df = get_data()
    total = len(df)

    projects = (
        int((df["category"] == "Project").sum())
        if total else 0
    )
    ppts = (
        int((df["category"] == "PPT").sum())
        if total else 0
    )
    learning = (
        int((df["category"] == "Learning").sum())
        if total else 0
    )

    a, b, c, d = st.columns(4)
    a.metric("Total Entries", total)
    b.metric("Projects", projects)
    c.metric("PPTs", ppts)
    d.metric("Learning Entries", learning)

    st.subheader("🕒 Recent Activity")

    if df.empty:
        st.info("No work entries yet.")
    else:
        for _, row in df.head(5).iterrows():
            display_entry(row)


# =========================================================
# 13. DASHBOARD + QUICK ADD
# =========================================================

elif page == "Dashboard":
    df = get_data()

    today_count = 0
    month_count = 0
    link_count = 0

    if not df.empty:
        today_count = len(
            df[df["work_date"].astype(str) == str(date.today())]
        )

        month_count = len(
            df[
                df["work_date"].astype(str).str.startswith(
                    date.today().strftime("%Y-%m")
                )
            ]
        )

        for column in [
            "github_url",
            "demo_url",
            "ppt_url",
            "linkedin_url",
        ]:
            link_count += int(
                df[column].fillna("").astype(str)
                .str.startswith(("https://", "http://"))
                .sum()
            )

    a, b, c, d = st.columns(4)
    a.metric("Total Entries", len(df))
    b.metric("Today's Entries", today_count)
    c.metric("This Month", month_count)
    d.metric("Links Saved", link_count)

    if is_owner:
        st.subheader("⚡ Quick Add")
        st.caption("Record your work and save your project links.")

        with st.expander(
            "➕ Add New Work / Project / Link",
            expanded=True,
        ):
            with st.form("add_work_form", clear_on_submit=True):
                work_date = st.date_input(
                    "Date",
                    value=date.today(),
                )

                category = st.selectbox(
                    "Category",
                    CATEGORIES,
                )

                title = st.text_input("Work title *")
                description = st.text_area("Tasks / notes")
                outcome = st.text_area("Achievement / result")
                skills = st.text_input("Tools / skills")

                hours = st.number_input(
                    "Hours spent",
                    min_value=0.0,
                    max_value=24.0,
                    value=0.0,
                    step=0.5,
                )

                status = st.selectbox("Status", STATUSES)

                st.markdown("#### 🔗 Project and Social Links")

                github_url = st.text_input("GitHub repository URL")
                demo_url = st.text_input("Live project URL")
                ppt_url = st.text_input("PPT / document URL")
                linkedin_url = st.text_input("LinkedIn post URL")

                next_step = st.text_input("Tomorrow's priority")

                submitted = st.form_submit_button(
                    "💾 Save Entry",
                    type="primary",
                    use_container_width=True,
                )

            if submitted:
                if not title.strip():
                    st.error("Please enter a work title.")
                else:
                    links = [
                        github_url,
                        demo_url,
                        ppt_url,
                        linkedin_url,
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
                            "Links must start with https:// or http://"
                        )
                    else:
                        entry_values = {
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
                            "next_step": next_step,
                        }

                        try:
                            save_entry(entry_values)
                            st.success("Entry saved successfully!")
                            st.rerun()

                        except Exception:
                            st.error(
                                "Unable to save this entry. "
                                "Open Manage app → Logs to see the "
                                "database error details."
                            )

    else:
        st.info(
            "You are viewing the public dashboard. "
            "Log in as owner to add, edit, or delete entries."
        )

    st.subheader("🕒 Recent Activity")

    if df.empty:
        st.info("No entries available yet.")
    else:
        for _, row in df.head(10).iterrows():
            display_entry(row, allow_edit=is_owner)


# =========================================================
# 14. ABOUT
# =========================================================

elif page == "About":
    st.subheader("About this portfolio")

    st.write(
        "This tracker records daily work, projects, presentations, "
        "LinkedIn posts, GitHub updates, learning, and achievements."
    )

    st.write(
        "Visitors can browse the portfolio without logging in. "
        "Only the owner can add, edit, or delete records."
    )


# =========================================================
# 15. MY WORK
# =========================================================

elif page == "My Work":
    st.subheader("📝 My Work & Achievements")

    search = st.text_input("🔎 Search all work")
    df = get_data(search=search)

    if df.empty:
        st.info("No work entries found.")
    else:
        st.caption(f"Total records: {len(df)}")

        for _, row in df.iterrows():
            display_entry(row, allow_edit=is_owner)


# =========================================================
# 16. CATEGORY PAGES
# =========================================================

elif page in [
    "Daily Work",
    "Projects",
    "PPT Tracker",
    "LinkedIn Posts",
    "GitHub Updates",
    "Learning",
]:
    category_map = {
        "Daily Work": "Daily Work",
        "Projects": "Project",
        "PPT Tracker": "PPT",
        "LinkedIn Posts": "LinkedIn Post",
        "GitHub Updates": "GitHub Update",
        "Learning": "Learning",
    }

    selected_category = category_map[page]

    st.subheader(f"📂 {page}")

    search = st.text_input("🔎 Search entries")
    df = get_data(
        category=selected_category,
        search=search,
    )

    if df.empty:
        st.info("No entries found in this category.")
    else:
        st.caption(f"Found {len(df)} entries")

        for _, row in df.iterrows():
            display_entry(row, allow_edit=is_owner)


# =========================================================
# 17. BACKUP
# =========================================================

elif page == "Backup":
    st.subheader("💾 Export Your Records")

    if not is_owner:
        st.info("Log in as owner to download your backups.")
    else:
        df = get_data()

        if df.empty:
            st.info("No entries to export yet.")
        else:
            st.download_button(
                "⬇️ Download CSV Backup",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name="daily_work_tracker.csv",
                mime="text/csv",
                use_container_width=True,
            )

            st.download_button(
                "⬇️ Download JSON Backup",
                data=df.to_json(
                    orient="records",
                    indent=2,
                    date_format="iso",
                ).encode("utf-8"),
                file_name="daily_work_tracker.json",
                mime="application/json",
                use_container_width=True,
            )

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

        st.warning(
            "Keep your database URL and owner password private. "
            "Export backups regularly."
        )


# =========================================================
# 18. FOOTER
# =========================================================

st.divider()
st.caption("Your work. Your progress. One place.")
