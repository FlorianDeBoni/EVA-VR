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
        
def add_feedback_sheet(
    service,
    spreadsheet_id: str,
    range_name: str,
    session_id: str,
    iteration: str,
    feedback: str,
) -> None:

    def _column_index_to_letter(index: int) -> str:
        """Convert 0-based column index to Excel-style column letter."""
        result = ""
        index += 1  # switch to 1-based
        while index:
            index, remainder = divmod(index - 1, 26)
            result = chr(65 + remainder) + result
        return result

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )

    rows = result.get("values", [])

    for index, row in enumerate(rows):
        if len(row) > 5 and row[2] == session_id and row[5] == iteration:

            sheet_row_number = index + 1

            # Find next empty column index
            next_column_index = len(row)

            # Convert column index to letter
            column_letter = _column_index_to_letter(next_column_index)

            update_range = f"{column_letter}{sheet_row_number}"

            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=update_range,
                valueInputOption="RAW",
                body={"values": [[feedback]]},
            ).execute()

            return