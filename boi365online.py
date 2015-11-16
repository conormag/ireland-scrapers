# -*- coding: latin-1 -*-
import requests
import json
import argparse
import re
from bs4 import BeautifulSoup
from requests import session

LOGIN1_URL = "https://www.365online.com/online365/spring/authentication?execution=e1s1"
LOGIN2_URL = "https://www.365online.com/online365/spring/authentication?execution=e1s2"

def clean_str(s):
    return ' '.join(s.split()).strip().replace("\n","").replace("\t","")

def is_acc_name(id):
    return id and re.compile("form:retailAccountSummarySubView[0-9]+:closedToggleControl").search(id)

def is_acc_balance(id):
    return id and re.compile("form:retailAccountSummarySubView[0-9]+:balance").search(id)

def is_loan_acc_name(id):
    return id and re.compile("form:nonRetailAccountSummarySubView[0-9]+:nonRetailAccountSummarySubView[0-9]+:outputPanel-[0-9]+").search(id)

def is_loan_acc_balance(id):
    return id and re.compile("form:retailAccountSummarySubView[0-9]+:balance").search(id)

def main():
    parser = argparse.ArgumentParser(description='Retrieve Bank Account history from Bank of Ireland www.365online.com. Output results in JSON.')
    parser.add_argument('userid', help='BoI 6 digit user id')
    parser.add_argument('dob', help='Date of Birth for the account in form DDMMYYYY')
    parser.add_argument('pin', help='6 digit PIN number for the account')
    parser.add_argument('phoneid', help='Last 4 digits of phone no.')

    args = parser.parse_args()

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.80 Safari/537.36'
    }

    with session() as c:
        def login():
            #get login page
            response = c.get(LOGIN1_URL,headers=headers)
            cookies = requests.utils.cookiejar_from_dict(requests.utils.dict_from_cookiejar(c.cookies))
            #print response.text.encode("utf-8")
            soup = BeautifulSoup(response.text, 'html.parser')

            payload = {
                "form:userId": args.userid,
                "form:ajaxRequestStatus": "AJAX REQUEST PROCESSOR INACTIVE",
                "form:j_id131:j_id146:contactPanelOpenedState": "",
                "form:j_id131:j_id146:contactUsPanelOpenedState": "",
                "form": "form",
                "autoScroll": "",
                "javax.faces.ViewState": "e1s1",
                "form:continue": "form:continue"
            }

            phone = soup.find('input', {"id": "form:phoneNumber"})
            if phone:
                payload["form:phoneNumber"] = args.phoneid
            else:
                payload["form:dateOfBirth_date"] = args.dob[:2] 
                payload["form:dateOfBirth_month"] = args.dob[2:4]
                payload["form:dateOfBirth_year"] = args.dob[4:]

            # login1 and get login2 page
            response  = c.post(LOGIN1_URL, headers=headers, data=payload,cookies=cookies)
            cookies = requests.utils.cookiejar_from_dict(requests.utils.dict_from_cookiejar(c.cookies))
            soup = BeautifulSoup(response.text, 'html.parser')

            pin_labels = ["form:security_number_digit" + str(n) for n in range(1, 7)]
            payload = {
                "form:ajaxRequestStatus": "AJAX REQUEST PROCESSOR INACTIVE",
                "form:j_id131:j_id146:contactPanelOpenedState": "",
                "form:j_id131:j_id146:contactUsPanelOpenedState": "",
                "form": "form",
                "autoScroll": "",
                "javax.faces.ViewState": "e1s2",
                "form:continue": "form:continue"
            }    

            for label in pin_labels:
                if soup.find('input', {"id": label}):
                    payload[label] = args.pin[int(label[-1:])-1]

            response  = c.post(LOGIN2_URL, headers=headers, data=payload, cookies=cookies)
            return response

        response = login()
        soup = BeautifulSoup(response.text, 'html.parser')

        # get the summary of accounts on first page
        a_keys=["Name","Balance"]
        accounts = [clean_str(name.get_text()) for name in soup.find_all(id=is_acc_name)]
        balances = [clean_str(name.get_text()) for name in soup.find_all(id=is_acc_balance)]
        account_list = [dict(zip(a_keys,i)) for i in zip(accounts,balances)]

        l_keys = ["Name","Balance","Description"]
        loans = [clean_str(name.get_text()) for name in soup.find_all(id=is_loan_acc_name)]
        loan_list = [dict(zip(l_keys,filter(None,re.split("^(.*?) eur ([0-9,.]+) (.*)$", loan)))) for loan in loans]

        print json.dumps(
            {"Summary": {"Accounts": account_list,"LoansAndMortgages": loan_list}},
            sort_keys=True,indent=4, separators=(',', ': '))


if __name__ == "__main__":
    main()

