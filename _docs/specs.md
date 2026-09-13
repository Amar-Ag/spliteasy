# SplitEasy — Product Specification

## Overview

SplitEasy is a web app for splitting shared expenses across multiple groups. Users create accounts, form groups, log expenses with custom splits, and track who owes whom until everyone is squared up.

## Features

### 1. User Accounts

- Register with email and password
- Login / logout
- Private access — no shared links, everything requires authentication

### 2. Groups

- Create a group with a name
- Invite members by email/username
- View all groups you belong to

### 3. Expenses

- Add an expense to a group (description, total amount, who paid)
- Split by custom amounts or percentages per member
- View expense history within a group

### 4. Balances & Settlements

- See a summary of who owes whom within a group
- Record a payment (e.g. "Bob paid Alice $20")
- Once settled, balances update to reflect the payment

## Tech Stack

- **Frontend:** React + TypeScript
- **Backend:** FastAPI (Python)
- **Database:** SQLite via SQLAlchemy
- **Auth:** JWT tokens
