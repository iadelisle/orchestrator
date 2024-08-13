import azure.functions as func
import logging
import requests
import os
import json
from bs4 import BeautifulSoup

## backend function services (context generator) ##


## backend prompt-flow endpoints, for query prompt generation ##

# AZ_FUNC_PROMPTFLOW_ENDPOINT = os.environ['AZFUNC_PROMPTFLOW_ENDPOINT']
# AZ_FUNC_PROMPTFLOW_KEY = os.environ['AZFUNC_PROMPTFLOW_KEY'] ## check if aoai key

# ## search service endpoints for querying context from manuals ##

# AZ_SEARCH_SERVICE_ENDPOINT = os.environ['AZ_SEARCH_SERVICE_ENDPOINT']
# AZ_SEARCH_SERVICE_INDEX = os.environ['AZ_SEARCH_SERVICE_INDEX']
# AZ_SEARCH_SERVICE_KEY = os.environ['AZ_SEARCH_SERVICE_KEY']

import re
from datetime import datetime, timedelta

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Mapping of full state names to their two-letter codes
state_name_to_code = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY"
}

def read_user_input_from_json(file_path):
    # Read JSON file and return as a dictionary
    with open(file_path, 'r') as file:
        json_data = json.load(file)
    return json_data

def extract_information(user_input):
    # Define possible event types
    possible_event_types = ["earthquake", "fire", "storm", "tsunami", "tornado", "hurricane", "flood", "volcano"]

    # Extract location and event type using simple string matching
    location = None
    event_type = None
    event_info = user_input


    # Use regex to find location (e.g., a state or city name)
    for state_name in state_name_to_code.keys():
        if re.search(rf'\b{state_name}\b', user_input, re.IGNORECASE):
            location = state_name_to_code[state_name]
            break

    # Determine the event type from the user input
    for event in possible_event_types:
        if event in user_input.lower():
            event_type = event
            break

    return event_info, location, event_type

def query_fema_website(state_code):
    # Use OpenFEMA API to get disaster declarations from the last 30 days for a specific state
    url = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
    
    # Calculate the date 30 days ago from today
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    params = {
        "$orderby": "declarationType asc",
        "$filter": f"declarationDate ge {thirty_days_ago} and state eq '{state_code}'",
        "$top": 100
    }


    response = requests.get(url, params=params)
    data = response.json()

    # Extract relevant information from the API response
    disasters = []
    for disaster in data['DisasterDeclarationsSummaries']:
        disasters.append({
            "femaDeclarationString": disaster.get('femaDeclarationString', ''),
            "disasterNumber": disaster.get('disasterNumber', ''),
            "state": disaster.get('state', ''),
            "declarationType": disaster.get('declarationType', ''),
            "declarationDate": disaster.get('declarationDate', ''),
            "fyDeclared": disaster.get('fyDeclared', ''),
            "incidentType": disaster.get('incidentType', ''),
            "declarationTitle": disaster.get('declarationTitle', ''),
            "incidentBeginDate": disaster.get('incidentBeginDate', ''),
            "incidentEndDate": disaster.get('incidentEndDate', ''),
            "disasterCloseoutDate": disaster.get('disasterCloseoutDate', ''),
            "fipsStateCode": disaster.get('fipsStateCode', ''),
            "fipsCountyCode": disaster.get('fipsCountyCode', ''),
            "placeCode": disaster.get('placeCode', ''),
            "designatedArea": disaster.get('designatedArea', ''),
            "declarationRequestNumber": disaster.get('declarationRequestNumber', ''),
            "lastIAFilingDate": disaster.get('lastIAFilingDate', ''),
            "lastRefresh": disaster.get('lastRefresh', '')
        })

    return disasters

def generate_index_json(fema_info):
    index = {
        "fema_information": fema_info
    }
    with open('index.json', 'w') as json_file:
        json.dump(index, json_file, indent=4)

def main():
    # Path to the JSON file containing user inputs
    json_file_path = "user_input.json"

    try:
        # Attempt to read user input from the JSON file
        user_input_data = read_user_input_from_json(json_file_path)
        user_input = user_input_data.get("user_input", "")
        print(f"User input read from JSON file: {user_input}")
    except FileNotFoundError:
        # Fall back to example user input if JSON file is not found
        user_input = "There is a hurricane in Florida."
        print(f"JSON file not found. Using manual input: {user_input}")

    # Extract information from user input
    event_info, location, event_type = extract_information(user_input)

    if location:
        fema_info = query_fema_website(location)
        generate_index_json(fema_info)
        print("Index JSON generated successfully.")
    else:
        print("Could not extract a valid location from the input.")




@app.route(route="generateCurrentDisasters")

def generateCurrentDisasters(req: func.HttpRequest) -> func.HttpResponse:

    ## query fema page and parse current disasters, return json object of current disasters for showing in frontend ##

    logging.info('Python HTTP trigger function processed a request.')


    url = 'https://www.fema.gov/disaster/current'
    resp = requests.get(url)

    logging.info('Request status code: %s', resp.status_code)



    disaster_links = []

    # Find the next siblings which are the disaster links
    soup = BeautifulSoup(resp.content, 'html.parser')

    links = soup.find_all('a', class_='fema-link')
    for link in links:
        href = link.get('href')  # Get the href attribute
        name = link.get_text(strip=True)  # Get the text inside the span tag
        disaster_links.append({'name': name, 'link': href})



    return func.HttpResponse(json.dumps(disaster_links), status_code=200)


# def contextOrchestrator(req: func.HttpRequest) -> func.HttpResponse:
#     logging.info('Python HTTP trigger function processed a request.')

#     body = req.get_json()
#     if body():
#         ## submit body text to context generator ##
        
#         event_info, location, event_type = extract_information(body)
        
#         ## submit body text to prompt-flow for query generation ##
#         if response.status_code == 200:

#             generated_query_response = requests.post(AZ_FUNC_PROMPTFLOW_ENDPOINT, headers={"x-functions-key": AZ_FUNC_PROMPTFLOW_KEY}, json=context_response_body)

#             query_response_body = generated_query_response.json()

#                     ## submit body text to search service for context generation ##
#             if response.status_code == 200:
                
#                 ## get back manuals from the search service ## 
#                 ## add search index to query response ## 

#                 query_response = requests.post(AZ_SEARCH_SERVICE_ENDPOINT, headers={"x-functions-key": AZ_SEARCH_SERVICE_KEY}, json=query_response_body)

#                 if query_response.status_code == 200:
#                     ## these are the returned manuals from the azure search service that we will provide to the web app for the few-shot prompt ##

#                     returnedManualChunks = query_response.json()

#                     ## process the azure search result to pass back to front end ##

#                     processed_chunks = process_search_response(returnedManualChunks)

#                     return func.HttpResponse(json.dumps(processed_chunks), status_code=200)


#                 else:
#                     return func.HttpResponse(
#                         "Error in search service query",
#                         status_code=400
#                     )


#             else:
#                 return func.HttpResponse(
#                     "Error in prompt generation",
#                     status_code=400
#                 )
            



#         else:
#             return func.HttpResponse(
#                 "Error in context generation",
#                 status_code=400
#             )

        

#     return func.HttpResponse(
#             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
#             status_code=200
#     )


# def process_search_response(jsonObj):
#     ## process the azure search result to pass back to front end ##

#     pass