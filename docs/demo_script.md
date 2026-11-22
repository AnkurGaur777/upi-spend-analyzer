# Video Walkthrough Narration Script: UPI & Bank Statement Spend Analyzer

**Target Duration:** ~2.5 to 3 minutes  
**Format:** Scene-by-scene presentation walkthrough  
**Tone:** Confident, data-driven, analytical, and structured  

---

## Scene 0: Introduction & Architecture (0:00 – 0:35)
**Visual:** Title Slide / Architecture Diagram (`docs/architecture.png`)

> *"Hello! Today I’m walking through my end-to-end portfolio project: the **UPI & Bank Statement Spend Analyzer**.*
>
> *Most people look at their bank statements or UPI transaction history and see hundreds of cryptic, noisy strings—like `UPI-SWIGGY-swiggy@icici-412345678901`—making it nearly impossible to answer a simple question: **'Where did my money actually go last month?'**
>
> *To solve this, I engineered a complete data pipeline using **Python, pandas, SQLAlchemy, and MySQL 8.0**, culminating in a multi-page **Power BI** analytical dashboard and an executive insights memo.*
>
> *The pipeline ingests raw multi-layout CSV and bank statements, normalizes merchant entities, filters out peer-to-peer transfers and reversals, classifies transactions using a priority-rule and fuzzy-matching engine with **100% evaluated accuracy**, detects recurring subscriptions, and loads everything into relational SQL views with guaranteed idempotency.*
>
> *Let’s dive straight into the findings across 12 months of transactions."*

---

## Scene 1: Executive Overview (0:35 – 1:15)
**Visual:** Page 1 (`powerbi/screenshots/01_overview.png`)

> *"Here on the **Executive Overview**, we see high-level cash flow across 704 processed transactions spanning October 2025 through September 2026.*
>
> *The top KPI cards immediately establish our macro baseline:*
> - *Total Earned Income was **₹7,80,000.00**, generated from a consistent net salary of ₹65,000 per month.*
> - *Operational Living Spend came out to **₹6,46,319.00**, which strictly excludes ₹60,000 in wealth-building mutual fund SIPs and own-account transfers.*
> - *This leaves **₹1,33,681.00** in retained savings, yielding a baseline **Annual Savings Rate of 17.1%**, with an average monthly spend of **₹53,860.00**.*
>
> *Looking at the clustered column chart, notice the monthly volatility in the secondary line. While our savings rate peaked at **30.5% in March 2026**, it dropped sharply to just **7.0% in November 2025** and **7.2% in July 2026**.*
>
> *On the right, we have interactive slicers allowing users to filter dynamically by reporting month or drill into specific expense categories."*

---

## Scene 2: Where It Goes – Categories & Merchants (1:15 – 1:55)
**Visual:** Page 2 (`powerbi/screenshots/02_where_it_goes.png`)

> *"Moving to the second page, **Where It Goes**, we decompose spending patterns across 10 distinct categories and identify vendor concentration.*
>
> *The horizontal bar chart highlights that **74.7% of all living spend** is concentrated in just four categories:*
> 1. ***Rent*** *is the single largest outlay at **₹2,16,000.00**—exactly **33.4%** of annual spend (₹18,000 fixed monthly payment).*
> 2. ***Groceries*** *takes **14.4%** at **₹92,979.00**, driven by regular supermarket and quick-commerce orders.*
> 3. ***Shopping*** *represents **14.0%** at **₹90,633.00**, primarily e-commerce purchases.*
> 4. ***Food & Dining*** *accounts for **12.9%** at **₹83,599.00**.*
>
> *Looking at the **Top 10 Merchants table** on the top right, our landlord Mr. Sharma, ATM cash withdrawals (₹54,000), Amazon (₹34,184), and Ajio (₹27,333) top the list.*
>
> *At the bottom, the **Month-over-Month Heat Matrix** reveals exactly why November 2025 suffered our savings rate trough: Shopping spiked by nearly ₹3,000 and Groceries spiked by over ₹4,300, driven by Diwali festive shopping and seasonal restocking."*

---

## Scene 3: Leaks & Subscriptions (1:55 – 2:30)
**Visual:** Page 3 (`powerbi/screenshots/03_leaks_subscriptions.png`)

> *"Page 3 focuses on operational leaks and recurring commitments.*
>
> *On the left, our automated detector surfaced all recurring debits meeting the median amount-tolerance rule (±5%). While total annual recurring commitments reach **₹3,06,804.00**, pure digital entertainment subscriptions amount to **₹9,216.00 / year**, consisting of Netflix at **₹7,788.00** and Spotify at **₹1,428.00**.*
>
> *On the top right, we quantify the **'Small-Ticket Leak'**—transactions under ₹300. Over 12 months, **229 micro-transactions quietly drained ₹43,887.00**.*
> - *The biggest culprit? **Transport**, with 125 daily cab, auto, and metro payments totaling **₹21,771.00**.*
> - *Second is impulse cafe and snack purchases, accounting for 71 debits totaling **₹14,722.00**.*
>
> *Below that, the column chart highlights online food delivery across Swiggy, Zomato, and Dominos: **129 orders totaling ₹51,565.00** (~11 orders a month), consuming **28.1% of all discretionary spend**."*

---

## Scene 4: Insights & Prioritized Recommendations (2:30 – 3:00)
**Visual:** Page 4 (`powerbi/screenshots/04_insights.png`)

> *"Finally, on Page 4, data analysis translates directly into business strategy.*
>
> *We summarize the 5 empirical findings on the left, and convert them into **3 high-impact, prioritized recommendations** on the right:*
>
> 1. ***Cap Online Food Delivery:*** *Limiting delivery orders to twice a week through weekend cooking saves **₹2,149.00 / month** (₹25,788/year).*
> 2. ***Review Streaming Subscriptions:*** *Pausing or cancelling Netflix and Spotify that you no longer need saves **₹768.00 / month** (₹9,216/year).*
> 3. ***Plug Micro-Transportation Leaks:*** *Replacing daily spontaneous cab hailings with a structured monthly Metro transit card saves **₹1,463.00 / month** (₹17,556/year).*
>
> *Combined, these 3 practical adjustments unlock **₹4,380.00 in monthly retained capital**, or **₹52,560.00 annually**.*
>
> *This single optimization lifts the annual savings rate from **17.1% to 23.9%**—a massive **+6.8 percentage point increase** without compromising quality of life.*
>
> *All numbers, code, and reproducible tests are publicly available in the repository. Thank you!"*
