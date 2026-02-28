from typing import Any

def write_google_sheet(service: Any, spreadsheet_id: str, range_name: str, body: dict) -> None:
    """
    Writes data to a Google Sheet.

    Parameters
    ----------
    service: Any
        The object to write on the sheet
    spreadsheet_id : str
        The ID of the Google Sheet to write to.
    range_name : str
        The A1 notation of the range to write to.
    values : dict
        A dictionnary {"values": List[List]} with the values to write to the specified range in the Google Sheet.

    Returns
    -------
    None
    """
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()