from polyline import polyline_database as pd
def extract_polyline(path):
    path_tuple = path.key()
    len(path_tuple)
    polyline = []
    for i in range(len(path_tuple)-1):
        poly_phase = path_tuple[i] + "-" + path_tuple[i+1]
        anti_polyphase = path_tuple[i+1] + "-" + path_tuple[i]
        for sub_path in pd.keys():
            if(poly_phase or anti_polyphase in pd.keys()):
                for points in pd[sub_path].values():
                    polyline.append(points)
    return polyline



        


