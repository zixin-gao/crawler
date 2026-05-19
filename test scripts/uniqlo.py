import requests
import json

def fetch_products():
    """
    Sends a POST request to the Uniqlo API to fetch product data.
    """
    # The API endpoint URL
    url = "https://uniqlo.com.hk/p/search/products/by-category"

    # The headers required by the API
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.uniqlo.com.hk",
        "Referer": "https://www.uniqlo.com.hk/",
        "langcode": "zh_HK",
        "Cookie": "sn3t4d1n=A8gpXzueAQAAJPzcogfuRoxBEOjT4v2C2_gFqn1KMe1bhtNMbAKCa2OTzb6jAW1uoskXThTdwH8AAEB3AAAAAA|1|0|b047d9de4f5d07dd4d2aa09009c352ac45bd0005; ktlvDW7IG5ClOcxYTbmY=a; _md_tempid=u930251779112551884; PIM-SESSION-ID=n4sNmoJC78oQo5D5; previousPageExists=true; bm_ss=ab8e18ef4e; ak_bmsc=527C6AC235D791506C29C376937F5640~000000000000000000000000000000~YAAQRT8uF6dF+BqeAQAAl5w2QB98lySReI1Za11Wf+Re+psCo4c++1F1vl9ki+1+eEbM8D9+2Fm8P6YPJDN1DfcpSb3bRaZwilGnhLHULMODLEYz6LtPKx2qEZiCAxRnndky2I3l68Tkgvrx46PdJ69BDzE+EEIpfhvpnBcmnkTKSVRRXcFcvJuW5nBVKVnGmtWZXi7zLt6Xxkw8wmjrGw9u+BE12BMoKPLfXGAvSIsit7M6tG+P9ljQfSHQmULOu4O+tZfm2SF6f7G5RcvZPlA6clZa9QbRp9S+b8z/4dGvvyYPBbiyqL8mBObz1RWgyiWzx5p+9myS6C37caNwk3+37bearBJXI75hmXeSaKkImcZ8ewxedzj+V4PUawFIFjzWhYttrhp88lL/rVc=; _md_tempid3=u108291779193824195; bm_lso=61008ABA7107ADA36161B2FC6C7C44C6F9F0ED8046083CE7E219818007D6EB21~YAAQsLkhF8ACOzCeAQAATgI9QAeXxfNNXW8nZp2HVm/jiP5ORBsDyR7vrg7wYSy+dytEDGk8uSAQ+DwvBs5H2MqsMiAeydfEzTfTL1LZ7Gup73buxF8yV1xxQDBvOFaAgmBE5NqK8jicOsL6NqGQhn73TR5v36OxKrbnvneFJbJqmB02aByRN/+Wdhlm5sOm5NTvELeGejpDx0D4f31ucm5BDLIg1FtMkQfRhFzTNOuyfA4OtvavBWkkPYr/D7Y2iUxaXEDG1iEdLmZd1d87q3Bi47TcCGop3mX4gvqf6v05SjuGD5UrrLxuXYehkn4oAugXUbspk0NioPvRy3c2tjE1iLCHXBz1EDIK/efEl6/4nwbKGHP3Ur3uaAPRuPCNpylDhxjagSe26YyNpNDWQ2yD1Jvop/3v8QxevLWFBn2KN3Z5Guvw/y0SLwCYSJHnb+QYa6JS8nWN//wULqRMb56xF4YOdXI=~1779194199540; bm_mi=563BCDBE64BCCBB17B9E519E888ECB19~YAAQsLkhF9N5OzCeAQAAwew9QB+MF6XyTogfhsqImcBnmRsaIYyXaWMFxO4DKqyD1ihGpmoaA3zfJnAdCemkkdlhojAdYj73x1Sno+/FIggTKuqNbRcKLC2SM3KifBPuKCChQP/O7rbpMYfaBlmdpu1xNjlAbicHxk7uFuusW/S47FU8rRtzzpFSE7S1QbX0hCOJy6PSuFd06qjmiv9yZJnA18WFDXLdU76yKmeZcOazePHPcz0Mr9JF9EQwn7j5qISsaobQY1Q5obyT7er28ma0SY3J3QDEixiNXsegopowBkacTvlOaYAcNk52USbmifg6I2Md3D/HM4L4BnD8~1; bm_s=YAAQsLkhF9R5OzCeAQAAwew9QAUzny9PAjB9WRXgIz6RXPQHqqL7O0MPxHuM0dtVB65WxlrUnxF0eRYhkQGRnSnJPPVPdWOcbH9WolXjICmvo3VfDwBJb8QOeba1xSeqrSJE8S+KNPYfcItP97BmJOhS1Dt3o9rmqu/8PPE6gmcD3KiezgXr+QxFgkoIujiUp1lsUWCyHshdOXPs9kKjyZdxyCV6dqCyIewZBBN+9LUh4w4TQmLaJhAe7UayohIYctU7A0MYa+QNEM1hSL1vqCbRTEh8u6mQ09mqU4pFkZ1toBjAxpTtM9sSuYkrz+a6vlUc5ao+ZdcLwZ8EEYWmg7SgjTAdMnU9RT7kevBce14Se2omw3NVwVaqZ4ztbWWZ5KBV/0gN45hXAyFnX7Cgdzg/TxL+j2zWNdpntqu4Ko9iwfhrsn/EmXndOP8LwiOYA/jl7RqNcPdsSMdhauLp43HhEMkik244mW2uqCPUyznTRZYebg2129RDwLW3/TWbywLxTwxPa/MWASfOCJjydmwPxu+yU6c4FTkgcwzXEYifeIEXGKu3Bm+AyBf9rwW6v3LoQfXNrYQOyVOKKEZGhkjUFNM7y6YnF4k8C/DdHrBapSjgXeDAS+L/HF6OHNtEXOLxVIdBky/Yx3UA5g71gaTV9JPxi5VV+uO7wTUiTb3ou8/mNCw+fiGpNThbzULEmwHVUIjU9RvfeTEMF+K5Kh4YNFj5U7peBrjX/2UVws1Hv/BcEtlziouvqlviB7O8RyVQ7qCXizb6vwe3+HfSVgVIl6LOnJ8nXalLpbOB1wj4lojLe8BhHkyx4GwHgKB4Zg5LK742IqTwgX907tzzKx0qLf0luwN9Tm0akP0SHAYF7WTNpe2qnRXDUfdQKG6I9Hc2hB8ykSksL81WsPiovREoE+nM07erCFk7Dr1SFqdicG4zLxeOuSMcriec5PFu+N1xoLaIXKg4tSXCSgAF0KWC; bm_so=7CA9669C1BB10C17A411B7EF8AE18D12749AFD7E0E92855EA80618103781A316~YAAQsLkhF9V5OzCeAQAAwew9QAdJlVklPxDLSvA1peIeMyWc3O6+gRvBXWLMrF0yyrH9KE+DW9J6MUT/62qmIwes6r3FX1JZaRCiag0fv4KBXpeY6rjjoofPyZbDhs7S3fCSk1l47rgY7mGE5bGyk5ykqTVFaxLas3+tMloCnyl6kMXGiPSwg69TlDtBQ1FnccULxQBI92PRTMMMErNNTOC3qnrXp7btnaXRwnVI2KvCj+3+pCfxlwI0iULWYFoRI0+BW1cO/OWlqy1Et+j3n7q84jWgGLsWc89oh0Cs7h2t1+t4VgCbr2nnvwNafY4Bhx25Yiv8DJ0AOrIaPev45FASHTX0cnuMe6QZnVGvYNBW2pc7ykaTexfZh9Ad90Ob9lQT4Hk+4YFaw7hySPD6RXTl0+34eXiGVEiGtKzcA0urqxFFZsyUMsUP+3/8Axr6YKIfn0fbkp4I7PCAd8lzvsKRf1GZyAI=; bm_sz=C320FF69A64AF52624CCF1EC03E16A7A~YAAQsLkhF9Z5OzCeAQAAwew9QB9+KVBPlc/g5GxqqKqGAWyKw4zl0X8IBvh30vWY7uf6SwZlen3eiOpiyBmuK0awrfPMHimF8di5cyryPn+69gZnAKa6Y8+Uld7zNx6McPCR08poo1bphk8DQu2XwUbFdzyojktbzM7BQUgzrsVvXeDG2KARHc5N9YUtgzcbl5rBLVYEvP9tNuLZ3r/43Lvnzx5pI98/FVVnbYqcRZ4g1OuBEEiZkwpf+jysG+4eHlWsQOSKxi9tj1cgakq/EAzEgtZk3P7tMPIha0EUOV8YPLkWFrfLHPHB7JA5SEjATweySWVsTJexL3tC7+W97uuVeaFZRGHzTWcNarK2cNCZrNMOckOtUoiG6//TUSay4uWmkCmr5lpWotvQtn3+X4vckLZ48RMaahW9UhB4mSR2YHpT/uw2NSDOjT8Zap4=~4272952~3683126; _abck=2AA7B713F3A329B84BDCAAC13617C42E~0~YAAQsLkhF356OzCeAQAA3O09QA+0iEX1nfAIINY0BNaLKWuSf3BlT4N1t7jOqBMzHLt3Ex80B/MU+Cl8felyEwBg4fSv+34zQya8J+hZ3nvAjuVNqGfSDxlyBsEnU8VDZBUkRSqG3/wLRdvmVHVpodQ8YZZ+YfqaJ9sCVOfyoG+N98qbWdMxjTz/becMeaNFyjU35JTLra7Mxu9Vny3AbV5ACx1T665Ww9rja62mqD+i122gx3ZHGFr4h0S6jdDlmybXlFw8lKIUGEgxw4KQmJzOMrQ1rg5fX6aXeWoGoQtVpe3Jg6Ga+8w17F+TzLdDR2MfGk3xo+0Jth58E+kQxLyD9sn7zicF9QQ0MKyOiyij0TsH4Pn/M6iFM41Na9YKB4KmD4pORoFJ6MDA2cxT9z3wSFwEcDllnjL8KkBpbjrOsbTzL2GkrYTg6QOfC5HbaJONe9BgVJTu9EfUtW8kaEH88grCKPryq98MHzucqvxpri4pTCxGbxA3ZtSDEgtxJDa8FiRx5+vNFXi5rZg4GhxWe9mOKLkJEUG/e8BjSUHGFhW8WPm0o0KYqdvUKWnWSrnWQ1FCsz8Bcd5tDUm1O8zLfyXdOB27na0c1jkD9Bg7Fkdw/mLKgRSjtTAvWcnYeYDr3EGkjgxb5Lks4maHfUi5OKw=~-1~-1~-1~AAQAAAAF%2f%2f%2f%2f%2f1AX3CEQW3dvb9+6wN1Y75nswMORuKLgItDzFOFPoP+btALhebWNSJYluNkZ5eTTBdCs6UJHmwR8xihEBScyuWY0a2o0CE5Iyy+L~-1; akavpau_www_uniqlo_com_hk_vp=1779194561~id=083b52ef79080219291bdb2ef36a55f3",
        # It's good practice to also include a User-Agent
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    # The payload (body) of the POST request
    payload = {
      "pageInfo": { "page": 1, "pageSize": 24 },
      "belongTo": "pc",
      "rank": "overall",
      "priceRange": { "low": 0, "high": 0 },
      "categoryCode": "all-women",
      "color": [],
      "size": [],
      "stockFilter": "warehouse",
      "searchFlag": False
    }

    try:
        # Send the POST request.
        # We use the `json` parameter to automatically serialize the payload and set the Content-Type header.
        response = requests.post(url, headers=headers, json=payload)
        print(f"posted!")

        # Raise an exception if the request returned an unsuccessful status code (4xx or 5xx)
        response.raise_for_status()
        print(f"get response")
        print(response)

        # Parse the JSON response
        data = response.json()        
        print(f"decode to json")

        # Print the results in a readable format
        print("Successfully fetched data. Here is the response:")
        # Use json.dumps for pretty-printing the dictionary
        print(json.dumps(data, indent=2, ensure_ascii=False))

        # Example: Print the name of the first product
        if data.get("resp", {}).get("result", {}).get("docs"):
            first_product = data["resp"]["result"]["docs"][0]
            print("\n--- Example: First Product ---")
            print(f"Name: {first_product.get('name')}")
            print(f"Price: {first_product.get('originPrice')}")
            print("----------------------------")


    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    fetch_products()