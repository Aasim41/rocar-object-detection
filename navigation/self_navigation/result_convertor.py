from .polyline import polypoints_db

def result_convertor(shortest_path_tuple):
    points = []
    for i, vertex in enumerate(shortest_path_tuple):
        points.append({
            "point": i + 1,
            "latitude": polypoints_db[vertex]["lats"],
            "longitude": polypoints_db[vertex]["longs"]
        })
    return points
