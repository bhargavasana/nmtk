
def recToArray(arr):
    return arr.view((float,len(arr.dtype.names)))

def toArray(fiter, varlist):
    return [tuple([row[var] for var in varlist]) for row in fiter]

def updateRow(row, field, val):
    row['properties'][field]=float(val)

def addResult(fiter, fields, value_array, array_fields):
    [updateRow(outrow, field, row[arr_field]) for outrow,row in zip(fiter.data_parsed['features'],value_array) for field,arr_field in zip(fields,array_fields)]




