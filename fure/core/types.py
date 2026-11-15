type JSONValue = (
    None | bool | dict[str, JSONValue] | float | int | list[JSONValue] | str
)

type JSONSchema = dict[str, JSONValue]
