from java import jclass

def get_location(params=None):

    try:

        PythonActivity = jclass(
            "org.beeware.android.MainActivity"
        )

        activity = PythonActivity.singletonThis

        Context = jclass("android.content.Context")

        location_manager = activity.getSystemService(
            Context.LOCATION_SERVICE
        )

        location = location_manager.getLastKnownLocation(
            "gps"
        )

        if location is None:

            location = location_manager.getLastKnownLocation(
                "network"
            )

        if location is None:

            return {
                "error": "No location available"
            }

        return {
            "latitude": location.getLatitude(),
            "longitude": location.getLongitude(),
            "accuracy": location.getAccuracy()
        }

    except Exception as e:

        return {
            "error": str(e)
        }
