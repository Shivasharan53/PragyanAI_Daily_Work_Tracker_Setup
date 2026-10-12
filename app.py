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

elif page == "Backup" and is_owner:
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
