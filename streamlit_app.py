
import os
from datetime import date
from typing import Any

import pandas as pd
import requests
import streamlit as st

# ---------------- Configuration ----------------
API_URL = os.getenv("API_URL", "https://agm-cable.onrender.com").rstrip("/")
API_TOKEN = os.getenv("APP_API_TOKEN", "")
TIMEOUT = 30

st.set_page_config(
    page_title="E-Recharge | Management",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------- Styling ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {font-family:'DM Sans',sans-serif;}
.stApp {background:#f5f7fc;}
.block-container {padding-top:1.5rem;padding-bottom:2.5rem;max-width:1500px;}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#151b3d 0%,#252e5c 100%);}
[data-testid="stSidebar"] * {color:#f8f9ff !important;}
[data-testid="stSidebar"] [data-testid="stRadio"] label {padding:9px 12px;border-radius:10px;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background:#ffffff18;}
div[data-testid="stMetric"] {background:#fff;border:1px solid #e8ebf4;border-radius:16px;padding:16px 18px;box-shadow:0 5px 18px #18234a0a;}
div[data-testid="stMetric"] label {color:#68718b;font-size:13px;font-weight:600;}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {color:#202b52;font-weight:800;}
.stButton>button {border-radius:10px;font-weight:600;min-height:40px;}
.stForm {background:#fff;border:1px solid #e8ebf4;border-radius:16px;padding:18px;}
[data-testid="stDataFrame"] {border:1px solid #e8ebf4;border-radius:12px;overflow:hidden;}
.hero {background:linear-gradient(115deg,#202a57,#4858a8);padding:24px 28px;border-radius:18px;color:white;margin-bottom:20px;box-shadow:0 10px 25px #26356820;}
.hero h2 {color:white;margin:0;font-size:26px;}
.hero p {color:#e1e6ff;margin:7px 0 0 0;font-size:14px;}
.small-note {color:#69738d;font-size:13px;}
</style>
""", unsafe_allow_html=True)


# ---------------- API helpers ----------------
class APIError(Exception):
    pass


def api_request(method: str, path: str, **kwargs) -> Any:
    headers = dict(kwargs.pop("headers", {}) or {})
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"

    try:
        response = requests.request(
            method=method,
            url=f"{API_URL}{path}",
            headers=headers,
            timeout=TIMEOUT,
            **kwargs,
        )
    except requests.ConnectionError as exc:
        raise APIError(
            f"Cannot connect to {API_URL}. Start FastAPI in another terminal."
        ) from exc
    except requests.Timeout as exc:
        raise APIError("The API request timed out. Please try again.") from exc
    except requests.RequestException as exc:
        raise APIError(f"Request failed: {exc}") from exc

    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except (ValueError, AttributeError):
            detail = response.text
        raise APIError(f"{response.status_code}: {detail}")

    if response.status_code == 204 or not response.content:
        return None

    try:
        return response.json()
    except ValueError:
        return response.text


def as_records(data: Any) -> list[dict]:
    if data is None:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("items", "results", "data", "recharges", "people", "history"):
            if isinstance(data.get(key), list):
                return [item for item in data[key] if isinstance(item, dict)]
        return [data] if data else []
    return []


def money(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def load_people(search: str = "") -> list[dict]:
    return as_records(
        api_request("GET", "/persons/", params={"search": search.strip()})
    )


def load_recharges(year: int, month: int, endpoint: str = "/recharges/") -> list[dict]:
    return as_records(
        api_request("GET", endpoint, params={"year": year, "month": month})
    )


def show_records_table(records: list[dict], key: str) -> None:
    if not records:
        st.info("No records found.")
        return

    df = pd.DataFrame(records)
    display_df = df.drop(columns=["payment_screenshot"], errors="ignore")
    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        key=key,
    )

    image_records = [
        (i, row.get("payment_screenshot"))
        for i, row in enumerate(records)
        if row.get("payment_screenshot")
    ]

    if image_records:
        with st.expander(f"View payment screenshots ({len(image_records)})"):
            labels = [
                f"Record {i + 1} — {records[i].get('name', records[i].get('person_name', 'Customer'))}"
                for i, _ in image_records
            ]
            selected = st.selectbox(
                "Select receipt", labels, key=f"{key}_receipt"
            )
            image_url = image_records[labels.index(selected)][1]

            try:
                headers = (
                    {"Authorization": f"Bearer {API_TOKEN}"}
                    if API_TOKEN else {}
                )
                image_response = requests.get(
                    image_url, headers=headers, timeout=TIMEOUT
                )
                image_response.raise_for_status()
                st.image(image_response.content, caption=selected, width=420)
            except requests.RequestException as exc:
                st.warning(f"Could not load screenshot: {exc}")


def download_csv(records: list[dict], filename: str, label: str) -> None:
    if records:
        csv_data = pd.DataFrame(records).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label,
            data=csv_data,
            file_name=filename,
            mime="text/csv",
        )


def month_year_controls(prefix: str) -> tuple[int, int]:
    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input(
            "Year",
            min_value=2000,
            max_value=2100,
            value=date.today().year,
            step=1,
            key=f"{prefix}_year",
        )
    with col2:
        month = st.selectbox(
            "Month",
            options=list(range(1, 13)),
            index=date.today().month - 1,
            key=f"{prefix}_month",
        )
    return int(year), int(month)

# ---------------- Sidebar / Header ----------------
st.sidebar.markdown("## ⚡ E-Recharge")
st.sidebar.caption("Recharge Management System")

page = st.sidebar.radio(
    "NAVIGATION",
    [
        "Dashboard",
        "Customer Management",
        "Add Customer",
        "Bulk Add Customers",
        "Recharge Payment",
        "Monthly Recharge",
        "Pending Recharge",
        "Paid Recharge",
        "Payment History",
        "Not Recharged",
        "Paid TV Numbers",
    ],
)

st.sidebar.divider()
st.sidebar.caption(f"Backend: {API_URL}")
st.sidebar.caption("Manage customers and monthly collections")

st.markdown("""
<div class="hero">
    <h2>⚡ E-Recharge Management</h2>
    <p>Customer records, monthly recharge tracking and payment collections in one place.</p>
</div>
""", unsafe_allow_html=True)


# ---------------- Dashboard ----------------
if page == "Dashboard":
    st.title("Dashboard")
    st.caption("Monthly collection overview")
    year, month = month_year_controls("dashboard")

    try:
        people = load_people()
        recharges = load_recharges(year, month)

        total_customers = len(people)
        required_total = sum(money(r.get("required_amount")) for r in recharges)
        paid_total = sum(money(r.get("amount_paid")) for r in recharges)
        pending_total = sum(
            max(money(r.get("required_amount")) - money(r.get("amount_paid")), 0)
            for r in recharges
        )
        fully_paid = sum(
            money(r.get("required_amount")) > 0
            and money(r.get("amount_paid")) >= money(r.get("required_amount"))
            for r in recharges
        )
        pending_count = max(len(recharges) - fully_paid, 0)

        cols = st.columns(4)
        cols[0].metric("Total Customers", f"{total_customers:,}")
        cols[1].metric("Fully Paid", f"{fully_paid:,}")
        cols[2].metric("Pending", f"{pending_count:,}")
        cols[3].metric("Collection", f"₹{paid_total:,.2f}")

        cols2 = st.columns(2)
        cols2[0].metric("Total Required", f"₹{required_total:,.2f}")
        cols2[1].metric("Pending Amount", f"₹{pending_total:,.2f}")

        st.subheader("Collection Summary")

        if recharges:
            summary = pd.DataFrame(
                {"Amount": [paid_total, pending_total]},
                index=["Collected", "Pending"],
            )
            st.bar_chart(summary)

            st.subheader("Monthly Recharge Records")
            show_records_table(recharges, "dashboard_recharges")
            download_csv(
                recharges,
                f"recharges_{year}_{month:02d}.csv",
                "Download monthly CSV",
            )
        else:
            st.info("No recharge records found for the selected month.")

    except APIError as exc:
        st.error(str(exc))


# ---------------- Customer Management ----------------
elif page == "Customer Management":
    st.title("Customer Management")
    search = st.text_input("Search by customer name")

    try:
        people = load_people(search)
        st.metric("Customers found", len(people))
        show_records_table(people, "customers_table")

        if people:
            st.subheader("Delete Customer")

            options = {
                f"{p.get('name', 'Customer')} | TV: {p.get('tv_number', '-')} | ID: {p.get('id')}": p.get("id")
                for p in people
            }

            selected = st.selectbox("Select customer", list(options.keys()))

            if st.button(
                "Delete customer and all recharge history",
                type="secondary",
            ):
                person_id = options[selected]

                try:
                    result = api_request("DELETE", f"/persons/{person_id}")
                    message = (
                        result.get("message", "Customer deleted.")
                        if isinstance(result, dict)
                        else "Customer deleted."
                    )
                    st.success(message)
                    st.rerun()
                except APIError as exc:
                    st.error(str(exc))

    except APIError as exc:
        st.error(str(exc))


# ---------------- Add Customer ----------------
elif page == "Add Customer":
    st.title("Add Customer")
    st.caption("Enter the customer's details below.")

    with st.form("add_customer_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        name = col1.text_input("Customer name *")
        phone = col2.text_input("Phone number")

        col3, col4 = st.columns(2)
        tv_number = col3.text_input("TV number *")
        place = col4.text_input("Place")

        submitted = st.form_submit_button("Add Customer", type="primary")

    if submitted:
        if not name.strip() or not tv_number.strip():
            st.error("Customer name and TV number are required.")
        else:
            try:
                result = api_request(
                    "POST",
                    "/persons/",
                    json={
                        "name": name.strip(),
                        "phone_number": phone.strip(),
                        "tv_number": tv_number.strip(),
                        "place": place.strip(),
                    },
                )
                st.success("Customer added successfully.")
                st.json(result)
            except APIError as exc:
                st.error(str(exc))
# ---------------- Bulk Add Customers ----------------
elif page == "Bulk Add Customers":
    st.title("Bulk Add Customers")
    st.caption("Add multiple customers in one submission.")

    default_data = pd.DataFrame([
        {"name": "", "phone_number": "", "tv_number": "", "place": ""}
    ])

    edited_data = st.data_editor(
        default_data,
        num_rows="dynamic",
        width="stretch",
        key="bulk_customer_editor"
    )

    if st.button("Add All Customers", type="primary"):
        records = edited_data.fillna("").to_dict(orient="records")
        customers = [
            {
                key: str(value).strip()
                for key, value in record.items()
            }
            for record in records
            if str(record.get("name", "")).strip()
        ]

        if not customers:
            st.error("Enter at least one customer name.")
        else:
            try:
                result = api_request(
                    "POST",
                    "/persons/bulk",
                    json=customers
                )
                st.success(f"Successfully added {len(result)} customers!")
                st.dataframe(pd.DataFrame(result), width="stretch")
            except APIError as exc:
                st.error(str(exc))

# ---------------- Recharge Payment ----------------
elif page == "Recharge Payment":
    st.title("Recharge Payment")
    st.caption("Add a payment or update an existing customer's monthly recharge.")

    try:
        people = load_people()

        if not people:
            st.warning("Add a customer before entering a recharge.")
        else:
            person_options = {
                f"{p.get('name')} | TV: {p.get('tv_number', '-')} | ID: {p.get('id')}": p.get("id")
                for p in people
            }

            with st.form("recharge_form"):
                selected_person = st.selectbox(
                    "Customer", list(person_options.keys())
                )

                col1, col2 = st.columns(2)
                year = col1.number_input(
                    "Year",
                    min_value=2000,
                    max_value=2100,
                    value=date.today().year,
                )
                month = col2.selectbox(
                    "Month",
                    list(range(1, 13)),
                    index=date.today().month - 1,
                )

                col3, col4 = st.columns(2)
                required_amount = col3.number_input(
                    "Required amount (₹)",
                    min_value=0.01,
                    value=150.0,
                    step=10.0,
                )
                amount_paid = col4.number_input(
                    "Amount paid (₹)",
                    min_value=0.0,
                    value=0.0,
                    step=10.0,
                )

                recharge_date = st.date_input(
                    "Recharge date", value=date.today()
                )
                recharged = st.checkbox("Recharge completed?", value=True)

                screenshot = st.file_uploader(
                    "Payment screenshot (JPG, PNG or WEBP; max 2 MB)",
                    type=["jpg", "jpeg", "png", "webp"],
                )

                submitted = st.form_submit_button(
                    "Save Recharge", type="primary"
                )

            if submitted:
                if screenshot and screenshot.size > 2 * 1024 * 1024:
                    st.error("Screenshot must be 2 MB or smaller.")
                else:
                    form_data = {
                        "person_id": str(person_options[selected_person]),
                        "year": str(year),
                        "month": str(month),
                        "required_amount": str(required_amount),
                        "amount_paid": str(amount_paid),
                        "recharged": str(recharged).lower(),
                        "recharge_date": recharge_date.isoformat(),
                    }

                    files = None
                    if screenshot:
                        files = {
                            "image": (
                                screenshot.name,
                                screenshot.getvalue(),
                                screenshot.type or "application/octet-stream",
                            )
                        }

                    try:
                        result = api_request(
                            "POST",
                            "/recharges/",
                            data=form_data,
                            files=files,
                        )
                        st.success("Recharge saved successfully.")

                        if isinstance(result, dict):
                            st.json(result)

                    except APIError as exc:
                        st.error(str(exc))

    except APIError as exc:
        st.error(str(exc))

# ---------------- Monthly Recharge ----------------
elif page == "Monthly Recharge":
    st.title("Monthly Recharge")
    year, month = month_year_controls("monthly")

    try:
        records = load_recharges(year, month)
        st.metric("Recharge records", len(records))
        show_records_table(records, "monthly_table")
        download_csv(
            records,
            f"monthly_recharges_{year}_{month:02d}.csv",
            "Download monthly recharge CSV",
        )
    except APIError as exc:
        st.error(str(exc))


# ---------------- Pending Recharge ----------------
elif page == "Pending Recharge":
    st.title("Pending Recharge")
    year, month = month_year_controls("pending")

    try:
        records = load_recharges(year, month, "/recharges/pending")

        pending_amount = sum(
            max(money(r.get("required_amount")) - money(r.get("amount_paid")), 0)
            for r in records
        )

        c1, c2 = st.columns(2)
        c1.metric("Pending records", len(records))
        c2.metric("Pending amount", f"₹{pending_amount:,.2f}")

        show_records_table(records, "pending_table")
        download_csv(
            records,
            f"pending_{year}_{month:02d}.csv",
            "Download pending CSV",
        )
    except APIError as exc:
        st.error(str(exc))


# ---------------- Paid Recharge ----------------
elif page == "Paid Recharge":
    st.title("Paid Recharge")
    year, month = month_year_controls("paid")

    try:
        records = load_recharges(year, month, "/recharges/paid")
        collection = sum(money(r.get("amount_paid")) for r in records)

        c1, c2 = st.columns(2)
        c1.metric("Fully paid records", len(records))
        c2.metric("Collection", f"₹{collection:,.2f}")

        show_records_table(records, "paid_table")
        download_csv(
            records,
            f"paid_{year}_{month:02d}.csv",
            "Download paid CSV",
        )
    except APIError as exc:
        st.error(str(exc))


# ---------------- Payment History ----------------
elif page == "Payment History":
    st.title("Payment History")

    try:
        people = load_people()

        if not people:
            st.info("No customers available.")
        else:
            person_options = {
                f"{p.get('name')} | TV: {p.get('tv_number', '-')}": p.get("id")
                for p in people
            }

            selected = st.selectbox(
                "Select customer", list(person_options.keys())
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                year = st.number_input(
                    "End year",
                    min_value=2000,
                    max_value=2100,
                    value=date.today().year,
                    key="history_year",
                )

            with col2:
                selected_month = st.selectbox(
                    "End month",
                    list(range(1, 13)),
                    index=date.today().month - 1,
                    key="history_month",
                )

            with col3:
                months = st.number_input(
                    "Number of months",
                    min_value=1,
                    max_value=60,
                    value=6,
                )

            if st.button("View Payment History", type="primary"):
                result = api_request(
                    "GET",
                    f"/persons/{person_options[selected]}/history",
                    params={
                        "year": int(year),
                        "selected_month": int(selected_month),
                        "months": int(months),
                    },
                )

                records = as_records(result)

                if records:
                    show_records_table(records, "history_table")
                    download_csv(
                        records,
                        f"payment_history_{year}_{selected_month:02d}.csv",
                        "Download history CSV",
                    )
                else:
                    message = (
                        result.get("message")
                        if isinstance(result, dict)
                        else None
                    )
                    st.info(message or "No payment history found.")

    except APIError as exc:
        st.error(str(exc))


# ---------------- Not Recharged ----------------
elif page == "Not Recharged":
    st.title("Not Recharged")
    st.caption(
        "Find customers who have no recharge record in one or more selected months."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        months = st.number_input(
            "Months to check", min_value=1, max_value=60, value=3
        )

    with col2:
        year = st.number_input(
            "End year",
            min_value=2000,
            max_value=2100,
            value=date.today().year,
            key="not_recharged_year",
        )

    with col3:
        month = st.selectbox(
            "End month",
            list(range(1, 13)),
            index=date.today().month - 1,
            key="not_recharged_month",
        )

    search = st.text_input(
        "Search customer (optional)",
        key="not_recharged_search",
    )

    if st.button("Find Not Recharged Customers", type="primary"):
        try:
            records = as_records(
                api_request(
                    "GET",
                    "/persons/not-recharged",
                    params={
                        "months": int(months),
                        "year": int(year),
                        "month": int(month),
                        "search": search.strip() or None,
                    },
                )
            )

            if records:
                display_records = []

                for record in records:
                    row = dict(record)
                    missing = row.get("not_recharged_months", [])

                    row["not_recharged_months"] = (
                        ", ".join(
                            f"{item.get('month')}/{item.get('year')}"
                            for item in missing
                        )
                        if isinstance(missing, list)
                        else str(missing)
                    )

                    display_records.append(row)

                show_records_table(
                    display_records,
                    "not_recharged_table",
                )
                download_csv(
                    display_records,
                    "not_recharged_customers.csv",
                    "Download CSV",
                )
            else:
                st.success(
                    "All matching customers have recharge records for the selected period."
                )

        except APIError as exc:
            st.error(str(exc))


# ---------------- Paid TV Numbers ----------------
elif page == "Paid TV Numbers":
    st.title("Paid TV Numbers")
    st.caption(
        "Export TV numbers for customers who fully paid in the selected month."
    )

    year, month = month_year_controls("tv_numbers")

    try:
        numbers = api_request(
            "GET",
            "/recharges/paid/tv-numbers",
            params={"year": year, "month": month},
        )

        if isinstance(numbers, list):
            st.metric("Fully paid TV numbers", len(numbers))

            tv_df = pd.DataFrame({"TV Number": numbers})

            st.dataframe(
                tv_df,
                width="stretch",
                hide_index=True,
            )

            st.download_button(
                "Download TV numbers CSV",
                data=tv_df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"paid_tv_numbers_{year}_{month:02d}.csv",
                mime="text/csv",
            )
        else:
            st.warning("Unexpected response from the TV numbers endpoint.")

    except APIError as exc:
        st.error(str(exc))
