# Data Inventory

## LendingClub Accepted Loans

- **Rows:** 2,260,701
- **Columns:** 151

| Column | Dtype | % Missing |
|---|---|---|
| id | object | 0.0 |
| member_id | float64 | 100.0 |
| loan_amnt | float64 | 0.0 |
| funded_amnt | float64 | 0.0 |
| funded_amnt_inv | float64 | 0.0 |
| term | object | 0.0 |
| int_rate | float64 | 0.0 |
| installment | float64 | 0.0 |
| grade | object | 0.0 |
| sub_grade | object | 0.0 |
| emp_title | object | 7.39 |
| emp_length | object | 6.5 |
| home_ownership | object | 0.0 |
| annual_inc | float64 | 0.0 |
| verification_status | object | 0.0 |
| issue_d | object | 0.0 |
| loan_status | object | 0.0 |
| pymnt_plan | object | 0.0 |
| url | object | 0.0 |
| desc | object | 94.42 |
| purpose | object | 0.0 |
| title | object | 1.03 |
| zip_code | object | 0.0 |
| addr_state | object | 0.0 |
| dti | float64 | 0.08 |
| delinq_2yrs | float64 | 0.0 |
| earliest_cr_line | object | 0.0 |
| fico_range_low | float64 | 0.0 |
| fico_range_high | float64 | 0.0 |
| inq_last_6mths | float64 | 0.0 |
| mths_since_last_delinq | float64 | 51.25 |
| mths_since_last_record | float64 | 84.11 |
| open_acc | float64 | 0.0 |
| pub_rec | float64 | 0.0 |
| revol_bal | float64 | 0.0 |
| revol_util | float64 | 0.08 |
| total_acc | float64 | 0.0 |
| initial_list_status | object | 0.0 |
| out_prncp | float64 | 0.0 |
| out_prncp_inv | float64 | 0.0 |
| total_pymnt | float64 | 0.0 |
| total_pymnt_inv | float64 | 0.0 |
| total_rec_prncp | float64 | 0.0 |
| total_rec_int | float64 | 0.0 |
| total_rec_late_fee | float64 | 0.0 |
| recoveries | float64 | 0.0 |
| collection_recovery_fee | float64 | 0.0 |
| last_pymnt_d | object | 0.11 |
| last_pymnt_amnt | float64 | 0.0 |
| next_pymnt_d | object | 59.51 |
| last_credit_pull_d | object | 0.0 |
| last_fico_range_high | float64 | 0.0 |
| last_fico_range_low | float64 | 0.0 |
| collections_12_mths_ex_med | float64 | 0.01 |
| mths_since_last_major_derog | float64 | 74.31 |
| policy_code | float64 | 0.0 |
| application_type | object | 0.0 |
| annual_inc_joint | float64 | 94.66 |
| dti_joint | float64 | 94.66 |
| verification_status_joint | object | 94.88 |
| acc_now_delinq | float64 | 0.0 |
| tot_coll_amt | float64 | 3.11 |
| tot_cur_bal | float64 | 3.11 |
| open_acc_6m | float64 | 38.31 |
| open_act_il | float64 | 38.31 |
| open_il_12m | float64 | 38.31 |
| open_il_24m | float64 | 38.31 |
| mths_since_rcnt_il | float64 | 40.25 |
| total_bal_il | float64 | 38.31 |
| il_util | float64 | 47.28 |
| open_rv_12m | float64 | 38.31 |
| open_rv_24m | float64 | 38.31 |
| max_bal_bc | float64 | 38.31 |
| all_util | float64 | 38.32 |
| total_rev_hi_lim | float64 | 3.11 |
| inq_fi | float64 | 38.31 |
| total_cu_tl | float64 | 38.31 |
| inq_last_12m | float64 | 38.31 |
| acc_open_past_24mths | float64 | 2.21 |
| avg_cur_bal | float64 | 3.11 |
| bc_open_to_buy | float64 | 3.32 |
| bc_util | float64 | 3.37 |
| chargeoff_within_12_mths | float64 | 0.01 |
| delinq_amnt | float64 | 0.0 |
| mo_sin_old_il_acct | float64 | 6.15 |
| mo_sin_old_rev_tl_op | float64 | 3.11 |
| mo_sin_rcnt_rev_tl_op | float64 | 3.11 |
| mo_sin_rcnt_tl | float64 | 3.11 |
| mort_acc | float64 | 2.21 |
| mths_since_recent_bc | float64 | 3.25 |
| mths_since_recent_bc_dlq | float64 | 77.01 |
| mths_since_recent_inq | float64 | 13.07 |
| mths_since_recent_revol_delinq | float64 | 67.25 |
| num_accts_ever_120_pd | float64 | 3.11 |
| num_actv_bc_tl | float64 | 3.11 |
| num_actv_rev_tl | float64 | 3.11 |
| num_bc_sats | float64 | 2.59 |
| num_bc_tl | float64 | 3.11 |
| num_il_tl | float64 | 3.11 |
| num_op_rev_tl | float64 | 3.11 |
| num_rev_accts | float64 | 3.11 |
| num_rev_tl_bal_gt_0 | float64 | 3.11 |
| num_sats | float64 | 2.59 |
| num_tl_120dpd_2m | float64 | 6.8 |
| num_tl_30dpd | float64 | 3.11 |
| num_tl_90g_dpd_24m | float64 | 3.11 |
| num_tl_op_past_12m | float64 | 3.11 |
| pct_tl_nvr_dlq | float64 | 3.12 |
| percent_bc_gt_75 | float64 | 3.34 |
| pub_rec_bankruptcies | float64 | 0.06 |
| tax_liens | float64 | 0.01 |
| tot_hi_cred_lim | float64 | 3.11 |
| total_bal_ex_mort | float64 | 2.21 |
| total_bc_limit | float64 | 2.21 |
| total_il_high_credit_limit | float64 | 3.11 |
| revol_bal_joint | float64 | 95.22 |
| sec_app_fico_range_low | float64 | 95.22 |
| sec_app_fico_range_high | float64 | 95.22 |
| sec_app_earliest_cr_line | object | 95.22 |
| sec_app_inq_last_6mths | float64 | 95.22 |
| sec_app_mort_acc | float64 | 95.22 |
| sec_app_open_acc | float64 | 95.22 |
| sec_app_revol_util | float64 | 95.3 |
| sec_app_open_act_il | float64 | 95.22 |
| sec_app_num_rev_accts | float64 | 95.22 |
| sec_app_chargeoff_within_12_mths | float64 | 95.22 |
| sec_app_collections_12_mths_ex_med | float64 | 95.22 |
| sec_app_mths_since_last_major_derog | float64 | 98.41 |
| hardship_flag | object | 0.0 |
| hardship_type | object | 99.52 |
| hardship_reason | object | 99.52 |
| hardship_status | object | 99.52 |
| deferral_term | float64 | 99.52 |
| hardship_amount | float64 | 99.52 |
| hardship_start_date | object | 99.52 |
| hardship_end_date | object | 99.52 |
| payment_plan_start_date | object | 99.52 |
| hardship_length | float64 | 99.52 |
| hardship_dpd | float64 | 99.52 |
| hardship_loan_status | object | 99.52 |
| orig_projected_additional_accrued_interest | float64 | 99.62 |
| hardship_payoff_balance_amount | float64 | 99.52 |
| hardship_last_payment_amount | float64 | 99.52 |
| disbursement_method | object | 0.0 |
| debt_settlement_flag | object | 0.0 |
| debt_settlement_flag_date | object | 98.49 |
| settlement_status | object | 98.49 |
| settlement_date | object | 98.49 |
| settlement_amount | float64 | 98.49 |
| settlement_percentage | float64 | 98.49 |
| settlement_term | float64 | 98.49 |

## PaySim Transactions

- **Rows:** 6,362,620
- **Columns:** 11

| Column | Dtype | % Missing |
|---|---|---|
| step | int64 | 0.0 |
| type | object | 0.0 |
| amount | float64 | 0.0 |
| nameOrig | object | 0.0 |
| oldbalanceOrg | float64 | 0.0 |
| newbalanceOrig | float64 | 0.0 |
| nameDest | object | 0.0 |
| oldbalanceDest | float64 | 0.0 |
| newbalanceDest | float64 | 0.0 |
| isFraud | int64 | 0.0 |
| isFlaggedFraud | int64 | 0.0 |

## Nifty 50 Prices

- **Rows:** 6,195
- **Columns:** 8

| Column | Dtype | % Missing |
|---|---|---|
| ticker | object | 0.0 |
| Date | object | 0.0 |
| Adj Close | float64 | 0.0 |
| Close | float64 | 0.0 |
| High | float64 | 0.0 |
| Low | float64 | 0.0 |
| Open | float64 | 0.0 |
| Volume | int64 | 0.0 |
