# Python Slack Clients

This library implements Slack client classes in Python, to simplify the programmatic use of Slack.

The original necessity covered here was a way to let a recurrent script update people on slack about findings and pending actions, without sending a very long slack message every time.

## `SlackClient`

The base class used for the others. Params for initialization are:

- `token`: Slack API token with permissions to access the workspace.
- `logger` (optional): logging.Logger object for logging messages.


## `SlackCanvasClient`
A client for interacting with Slack Canvas. Params for initialization are:

- `token`: Slack API token with permissions to access the canvas.
- `canvas_id`: The ID of the Slack canvas to interact with.
- `logger` (optional): `logging.Logger` object for logging messages.

## `SlackListClient`
A client for interacting with Slack lists that supports adding, removing, 
and (un)completing items. Params for initialization are:

- `token`: Slack API token with permissions to access the list.
- `logger` (optional): `logging.Logger` object for logging messages.
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

Webhook URLs are obtained by editing the "Start the workflow..." step, and have a format like this: (X are alphanumeric characters, 0 are digits, and H are hexadecimal characters)

```
https://hooks.slack.com/triggers/XXXXXXXXX/0000000000000/HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH
```

## Other functionality not implemented

Lists in slack also allow assignment to a person and setting a due date, but limitations in what slack workflows allow a proper interface could not be implemented in `SlackListClient`.

A client for working with CSV files was also attempted but was deemed impractical due to how files work in slack - we can't replace a file, we can just delete and recreate it, so even if the functionality could concievably be coded it would not be properly ergonomic in slack itself.