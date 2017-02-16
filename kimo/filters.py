def apply_filters(processes, filters):
    """
    Apply filters on list of dictionaries.
    If multiple filters given they will be ANDed.

    >> l = [
    >>     {'ID': '1234', 'Host': 'worker-1', 'Time': 12},
    >>     {'ID': '5555', 'Host': 'worker-2', 'Time': 2},
    >> ]
    >> filters = [{'ID': 1234}]
    >> apply_filters(l, filters)
    .. [{'ID': '1234', 'Host': 'worker-1', 'Time': 12}]

    """
    for process in processes:
        for key, value in filters:
            if getattr(process, key) != value:
                break
        else:
            yield process
