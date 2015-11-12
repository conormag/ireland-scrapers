import sys
import requests
import json
import argparse
import csv
from bs4 import BeautifulSoup
from requests import session

BASE            = "https://www.cu247.ie/"
INDEX_ROUTE     = "/"
LOGIN_ROUTE     = "/login/do"
MAIN_ROUTE      = "/cu247"
TRANS_ROUTE     = "/cu247/transactions"
LOGOUT_ROUTE    = "/login/logout"
UA              = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.80 Safari/537.36"

def main():
    parser = argparse.ArgumentParser(description='Retrieve Credit Union account details from www.cu247.ie. Output results in JSON.')
    parser.add_argument('cu_id', help='Credit Union Identifier [Example: mervue]')
    parser.add_argument('user_id', help='"Web User Id" for the account')
    parser.add_argument('pin', help='PIN number for the account')

    args = parser.parse_args()

    BASE_URL        = BASE + args.cu_id
    FP_URL          = BASE_URL + INDEX_ROUTE
    LOGIN_URL       = BASE_URL + LOGIN_ROUTE
    OVERVIEW_URL    = BASE_URL + MAIN_ROUTE
    TRANSACTION_URL = BASE_URL + TRANS_ROUTE
    LOGOUT_URL      = BASE_URL + LOGOUT_ROUTE

    FORM_SELECTOR       = INDEX_ROUTE + args.cu_id + TRANS_ROUTE 
    OVERVIEW_SELECTOR   = INDEX_ROUTE + args.cu_id + MAIN_ROUTE

    def return_to_overview_seq(page):
        form = page.find('form', {"action": OVERVIEW_SELECTOR})
        seq = form.find('input', {"name": "seq"}).get("value")
        return seq

    def get_statement(page):
        table = page.find_all('table', {'class': 'list'})
        table = table[1] if len(table) == 2 else table[0]

        statement = []
        theaders = [header.string for header in table.find_all("th")]
        for row in table.find_all("tr"):
            cells = row.select("td")
            statement.append({theaders[i]: cell.string.strip() for i, cell in enumerate(cells)})
        return statement

    headers = { 'User-Agent': UA }

    with session() as c:
        # get login page
        response = c.get(FP_URL, headers=headers)
        if response.status_code != requests.codes.ok:
            sys.exit('Cant access page at "{}". Exiting with HTTP Status {}. '.format(FP_URL, response.status_code))
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            if not soup.find('div', {'class': 'login-form'}):
                sys.exit('No login form. Is "{}" a valid Credit Union?'.format(args.cu_id))

        seq = soup.find('input', {'name': 'seq'}).get('value')

        payload = {
            "submit": "Login",
            "username": args.user_id,
            "password": args.pin,
            "seq": seq
        }

        # login and get summary page
        response  = c.post(LOGIN_URL, headers=headers, data=payload)
        soup = BeautifulSoup(response.text, 'html.parser')
        cookies = requests.utils.cookiejar_from_dict(requests.utils.dict_from_cookiejar(c.cookies))

        # if invalid credentials supplied, there will be a message div.
        msg = soup.find('div', {'class': 'message'})
        if msg:
            sys.exit(msg.string.strip())

        table = soup.find('table', {'class': 'list'})

        accounts = []
        theaders = [header.string for header in table.select("tr th")]
        for row in soup.find_all("tr"):
            cols = row.select("td")
            if len(cols) == 4:
                accounts.append({theaders[i]: cell.string.strip() for i, cell in enumerate(cols)})

        trans_payload = {}
        for account in accounts:
            # find the form post for this account
            forms = soup.find_all('form', {"action": FORM_SELECTOR})
            for form in forms:        
                payload = {el.get('name'): el.get('value') for el in form.find_all("input")}
                if payload["accNum"] == account["Account #"]:
                    trans_payload = payload

            response  = c.post(TRANSACTION_URL, headers=headers, data=trans_payload)
            page = response.text

            # fix an error where there is an erroneous </td> in each table row
            page = page.replace("</td>\n    </td>","</td>")
            soup = BeautifulSoup(page, 'html.parser')
            
            seq = return_to_overview_seq(soup)
            account["statement"] = get_statement(soup)

            # return to main page
            payload = {"seq": seq, "submit":"Return to Balances"}
            response  = c.post(OVERVIEW_URL, headers=headers, data=payload)
            soup = BeautifulSoup(response.text, 'html.parser')

        #logout
        payload = {"transactionsButton":"Logout"}
        response  = c.post(LOGOUT_URL, headers=headers, data=payload,cookies=cookies)

        print json.dumps({"accounts": accounts},sort_keys=True,indent=4, separators=(',', ': '))

if __name__ == "__main__":
    main()
