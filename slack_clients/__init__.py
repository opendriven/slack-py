# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "slack-sdk==3.35.0",
#   "requests>=2",
#   "isodate>=0.7.2",
# ]
# ///

from os import getenv as os_getenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse
from csv import DictReader as csv_DictReader #, DictWriter as csv_DictWriter
from requests import get as requests_get, post as requests_post
#from datetime import datetime
from isodate import parse_date
import logging
from re import match as re_match
from sys import stdout as sys_stdout#, stderr as sys_stderr

if __name__ == "__main__":
    print("This script is designed to be run as a module, not directly.")


class SlackClient:
    """
    A Base client for interacting with Slack. Initialization requires:
    - `token`: Slack API token with permissions to access the workspace.
    - `logger`: Optional logging.Logger object for logging messages.
    """
    def __init__(self, token: str, logger: logging.Logger|None = None):
        self.client: WebClient = WebClient(token=token)
        if logger is None:
            logging.basicConfig(level=os_getenv("LOG_LEVEL", "INFO"),handlers=[
                logging.StreamHandler(sys_stdout),
                logging.FileHandler("debug.log")]
            )
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logger

    def send_message(self, channel: str, text: str) -> None:
        try:
            response = self.client.chat_postMessage(channel=channel, text=text)
            self.logger.info(f"Message sent successfully: {response['ts']}")
        except SlackApiError as e:
            self.logger.error(f"Error sending message: {e.response['error']}")
            raise e
    
    # def send_message_list(self, channel:str, text:str, items:list) -> None:
    #     formatted_items = "\n".join(f"- {item}" for item in items)
    #     full_text = f"{text}\n\n{formatted_items}"
    #     print("Sending message to Slack...")
    #     print(f"Channel: {channel}")
    #     print(f"Message:\n{full_text}")
    #     self.send_message(channel, full_text)


################################################################################################################################
################################################################################################################################
################################################################################################################################

class SlackCanvasClient(SlackClient):
    """
    A client for interacting with Slack Canvas. Initialization requires:
    - `token`: Slack API token with permissions to access the canvas.
    - `canvas_id`: The ID of the Slack canvas to interact with.
    - `logger`: Optional `logging.Logger` object for logging messages.
    """
    def __init__(self, token: str, canvas_id: str, logger:logging.Logger|None = None):
        super().__init__(token=token, logger=logger)
        self.canvas_id = canvas_id

    def update_canvas(self, markdown_content:str):
        """
        Updates the Slack canvas with the given markdown content.
        :param markdown: The markdown content to update the canvas with.
        """
        self.client.canvases_edit(
            canvas_id=self.canvas_id,
            changes=[{
                'operation':'replace',
                'document_content':{
                    'type':'markdown',
                    'markdown':markdown_content
                    }
                }]
            )
    
    def canvas_info(self) -> dict:
        """
        Fetches information about the Slack canvas.
        :return: A dictionary containing the canvas information retrieved using files_info().
        :raises SlackApiError: If there is an error fetching the canvas information.
        """
        try:
            response: SlackResponse = self.client.files_info(file=self.canvas_id)
            if response.status_code != 200:
                raise SlackApiError(message=f"Failed to fetch canvas info: {response.status_code} {response.data}", response=response)   
        except SlackApiError as e:
            self.logger.error(f"Error fetching canvas info: {e.response['error']}")
            raise e
        return response.data['file'] # type: ignore
    
    def canvas_permalink(self) -> str:
        """
        Returns the permalink to the Slack canvas.
        :return: The permalink to the canvas.
        :raises SlackApiError: If there is an error fetching the canvas information.
        """
        info = self.canvas_info()
        if 'permalink' not in info:
            raise SlackApiError("Canvas does not have a permalink.", response=None)
        return info['permalink']

################################################################################################################################
################################################################################################################################
################################################################################################################################

class SlackListClient(SlackClient):
    """
    A client for interacting with Slack lists that supports adding, removing, 
    and (un)completing items. Initialization requires:
    - `token`: Slack API token with permissions to access the list.
    - `logger`: Optional `logging.Logger` object for logging messages.
    - `list_id`: The ID of the Slack list to interact with.
    - `webhook_add`: The URL for the webhook to add items to the list.
    - `webhook_delete`: The URL for the webhook to delete items from the list.
    - `webhook_complete` (optional): The URL for the webhook to check or un-check the "completed" checkbox on items in the list.
    The webhooks should correspond to existing workflows in Slack that 
    handle adding and deleting items from the list::
    ### workflow for `webhook_add`:
    - start the workflow with a webhook (`webhook_add` is the URL for this)
        - takes the "name" parameter
    - action: add an item to the list, with Name = `name` (other fields empty)
    ### workflow for `webhook_delete`:
    - start the workflow with a webhook (`webhook_delete` is the URL for this)
        - takes the "name" parameter
    - action: select a list item by Name = `name`
    - action: delete a list item, selected by the previous step
    ### workflow for `webhook_complete`:
    - start the workflow with a webhook (`webhook_complete` is the URL for this)
        - takes the "name" parameter
        - takes the "completed" parameter (should be "Yes" or "No")
    - action: select a list item by Name = `name`
    - action: update a list item, selected by the previous step, setting "Completed" to `completed`

    Webhook URLs are obtained by editing the "Start the workflow..." step, and have a format like this:
    ```
    https://hooks.slack.com/triggers/XXXXXXXXX/0000000000000/HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH
    ```
    X are alphanumeric characters, 0 are digits, and H are hexadecimal characters
    """
    def __init__(self, token: str, list_id: str,
                webhook_add: str, webhook_delete: str, webhook_complete: str|None = None, logger:logging.Logger|None = None):
        super().__init__(token=token, logger=logger)
        self.list_id: str = list_id
        for wh in ["webhook_add", "webhook_delete"]:
            if not self.__validate_slack_webhook(locals()[wh]):
                raise ValueError(
                    f"{wh} is an invalid Slack webhook URL: {locals()[wh]}")
        if webhook_complete is not None and not self.__validate_slack_webhook(webhook_complete):
            raise ValueError(
                f"webhook_complete is an invalid Slack webhook URL: {webhook_complete}")
        self.webhook_add: str = webhook_add
        self.webhook_delete: str = webhook_delete
        self.webhook_complete: str|None = webhook_complete

    def __validate_slack_webhook(self,url:str) -> bool|None:
        """
        Validates if the given URL is a valid Slack webhook URL. We're expecting 
        something like:
        ```
        https://hooks.slack.com/triggers/XXXXXXXXX/0000000000000/HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH
        ```
        X are alphanumeric characters, 0 are digits, and H are hexadecimal characters
        
        :param url: The URL to validate.
        :return: `True` if the URL is a valid Slack webhook URL, `None` if url is `None`, `False` otherwise.
        """
        if url is None:
            return None
        else:
            regex = r'^https://hooks\.slack\.com/triggers/[A-Za-z\d]+/\d+/[A-Fa-f\d]+$'
            return re_match(regex, url) is not None

    def __parse_bool_str(self,value: str) -> bool:
        """
        Parses a string value to a boolean.
        Accepts "true" or "false" (case-insensitive).
        :param value: The string value to parse.
        :return: True if the value is "true", False if the value is "false".
        """
        return value.lower() == 'true' if value else False

    def __parse_date_str(self, value: str): 
        """
        Parses a string value to a date in ISO format (`YYYY-MM-DD`).
        If the value is empty, returns `None`.

        :param value: The string value to parse.
        :return: A `datetime.date` object if the value is in the correct format, 
        otherwise `None`.
        """
        if not value:
            return None
        try:
            return parse_date(value)
        except Exception:
            self.logger.error(f"Invalid date format: {value}")
            return None


    def get_list_items(self) -> list[dict]:
        """
        Fetches the list items from the Slack list. The expected result is a list 
        of dicts with the following fields:
        - `Name` (str): The name of the item.
        - `Completed` (bool): Whether the item is completed.
        - `Assignee` (str, an email): The assignee of the item.
        - `Due Date` (datetime): The due date of the item.
        :return: A list of dictionaries representing the items in the list.
        """
        # TODO: error handling for requests and csv reader
        url = self.client.files_info(file=self.list_id).data['file']['list_csv_download_url'] # type: ignore
        resp = requests_get(url, headers={"Authorization": f"Bearer {self.client.token}"})
        csv_reader = csv_DictReader(resp.text.splitlines())
        return [{
            'Name': row['Name'],
            'Completed': self.__parse_bool_str(row['Completed']),
            'Assignee': row['Assignee'] if row['Assignee'] else None,
            'Due Date': self.__parse_date_str(row['Due Date'])
            } for row in csv_reader]
    
    def add_item(self, item:str):
        """
        Adds an item by sending a POST request to the webhook on 
        `self.webhook_add`. This function only triggers the worflow, any local 
        copy of the list must be updated separately.

        :param item: The item to add.
        """
        if len([i for i in self.get_list_items() if i['Name'] == item]) > 0:
            self.logger.warning(f"Item '{item}' already exists in the list.")
            return
            # raise error?
        #self.logger.info(f"Adding item '{item}' to the list...")
        resp = requests_post(url=self.webhook_add, json={"name": item})
        if resp.status_code == 200:
            self.logger.info(f"{item} added to the list successfully")
        else:
            self.logger.error(f"Error while adding item '{item}' to the list: {resp.status_code} {resp.text}")
        
        
    def delete_item(self, item:str):
        """
        Deletes an item by sending a POST request to the webhook on 
        self.webhook_delete. This function only triggers the worflow, any local 
        copy of the list must be updated separately.

        :param item: The item to delete.
        """
        if len([i for i in self.get_list_items() if i['Name'] == item]) == 0:
            self.logger.warning(f"Item '{item}' does not exist in the list.")
            return
            # raise error?
        #print(f"Deleting item '{item}' from the list...", end="")
        resp = requests_post(url=self.webhook_delete, json={"name": item})
        if resp.status_code == 200:
            self.logger.info(f"Item '{item}' deleted from the list successfully")
            #print("Done ✅")
        else:
            self.logger.error(f"Error while deleting item '{item}' from the list: {resp.status_code} {resp.text}")
            #print("Error ❌")

    def complete_item(self,item:str, complete:bool = True):
        """
        Checks (if `checked` is true) or unchecks (if `checked` is false) the 
        "Completed" checkbox of an item in the list by sending a POST request to 
        the webhook on self.webhook_complete.
        :param item: The item to check or uncheck.
        :param complete: Whether to check (True) or uncheck (False) the "Completed" checkbox.
        """
        if not self.webhook_complete:
            self.logger.error(
                "Webhook for completing items is not set. Cannot complete or un-complete items.")
            raise ValueError(
                "Webhook for completing items is not set. Cannot complete or un-complete items.")
        items_filtered = [i for i in self.get_list_items() if i['Name'] == item]
        if len(items_filtered) == 0:
            self.logger.warning(f"Item '{item}' does not exist in the list.")
            return
        if complete and items_filtered[0]['Completed']:
            self.logger.info(f"Item '{item}' is already completed.")
            return
        elif not complete and not items_filtered[0]['Completed']:
            self.logger.info(f"Item '{item}' is already not completed.")
            return
        _ing = "Completing" if complete else "Un-completing"
        #self.logger.info(f"{_ing} item '{item}' in the list...")
        completed_str = 'Yes' if complete else 'No'
        resp = requests_post(url=self.webhook_complete, 
            json={"name": item, "completed": completed_str})
        if resp.status_code == 200:
            self.logger.info(f"Item '{item}' {'completed' if complete else 'un-completed'} successfully")
            #print("Done ✅")
        else:
            self.logger.error(f"Error while {'completing' if complete else 'un-completing'} item '{item}': {resp.status_code} {resp.text}")
            #print("Error ❌")

    def update_list(self, new_list: list[str], uncomplete: bool = True):
        """
        Updates the Slack list to contain the items in `new_list`.
        
        This function is expensive since it calls the Slack API multiple times.
        Also note that we can't check for proper completion of the workflows, 
        we just call the webhooks and hope for the best.

        :param new_list: The new list of items to update the Slack list with.
        :param uncomplete: Whether to un-complete items that are in the new list but marked as completed. Defaults to True.
        """
        old_list = self.get_list_items()
        for i in old_list:
            if i['Name'] not in new_list:
                self.delete_item(i['Name']) # delete item not in new_list
            elif i['Name'] in new_list and i['Completed'] and uncomplete:
                self.complete_item(i['Name'], complete=False) # un-complete item in new_list that is marked as completed
        for i in new_list:
            if i not in [i['Name'] for i in old_list]:
                self.add_item(i) # add item in new_list that is not in old_list
            
    def clear_list(self):
        """
        Clears the Slack list by deleting all items in it.
        
        This function is expensive since it calls the Slack API multiple times.
        """
        self.logger.info("Clearing the Slack list...")
        for item in self.get_list_items():
            self.delete_item(item['Name'])
        self.logger.info("Done clearing the Slack list.")

