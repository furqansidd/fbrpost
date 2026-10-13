import os
import pytest
from src.parser import parse_and_validate_tax_data

def test_parse_mohammad_azhar_excel():
    excel_path = "Mohammad Azhar - Plastic (149).xls"
    assert os.path.exists(excel_path)
    data = parse_and_validate_tax_data(excel_path, tax_year=2026)
    
    # Check income statement figures
    assert data["income"]["3029"] == 56254810.0   # Net Revenue
    assert data["income"]["3039"] == 465320.0     # Opening Stock
    assert data["income"]["3059"] == 49541580.0   # Purchases
    assert data["income"]["3071"] == 2025480.0    # Wages & Benefits
    assert data["income"]["3073"] == 1104524.0    # Electricity
    assert data["income"]["3099"] == 475120.0     # Closing Stock
    assert data["income"]["gross_profit"] == 3593026.0

    # Check expenses
    assert data["expenses"]["3154"] == 1020000.0  # Staff Salaries
    assert data["expenses"]["3155"] == 37587.0    # Travelling
    assert data["expenses"]["3162"] == 8750.0     # Telephone
    assert data["expenses"]["3166"] == 3750.0     # Stationery
    assert data["expenses"]["3171"] == 10000.0    # Professional Charges
    assert data["expenses"]["3172"] == 3258.0     # Bank Charges
    assert data["expenses"]["total_expenses"] == 1124191.0
    assert data["income"]["net_income"] == 2468835.0

    # Check balance sheet
    assert data["balance_sheet"]["3303"] == 1525600.0  # Machinery
    assert data["balance_sheet"]["3315"] == 465320.0   # Stock
    assert data["balance_sheet"]["3319"] == 209080.0   # Cash
    assert data["balance_sheet"]["3352"] == 2200000.0  # Capital

    # Check wealth assets
    assert data["wealth"]["properties"]["total"] == 16325000.0
    assert data["wealth"]["banks"]["total"] == 3519048.0
    assert data["wealth"]["banks"]["scb"] == 259568.0
    assert data["wealth"]["banks"]["meezan"] == 3259480.0
    assert data["wealth"]["cash_in_hand"] == 5037462.0
    assert data["wealth"]["liabilities"]["loan_sharif"] == 5000000.0

    # Check personal expenses & reconciliation
    assert data["wealth"]["personal_expenses"] == 558605.0
    assert data["wealth"]["reconciled"] is True
    assert data["wealth"]["difference"] == 0.0

    # Check tax deductions
    assert data["tax_deductions"]["fesco_235"] == 62682.0
    assert data["tax_deductions"]["property_236k"] == 68498.0
    assert data["tax_deductions"]["internet_mobile"] == 3109.0
