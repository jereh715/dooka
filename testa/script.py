from java import jclass

def get_location(params=None):

    try:

        PythonActivity = jclass(
            "org.beeware.android.MainActivity"
        )

        activity = PythonActivity.singletonThis

        Context = jclass("android.content.Context")
        PackageManager = jclass(
            "android.content.pm.PackageManager"
        )

        ActivityCompat = jclass(
            "androidx.core.app.ActivityCompat"
        )

        Manifest = jclass(
            "android.Manifest"
        )

        permission = Manifest.permission.ACCESS_FINE_LOCATION

        # Check permission
        granted = (
            ActivityCompat.checkSelfPermission(
                activity,
                permission
            )
            == PackageManager.PERMISSION_GRANTED
        )

        if not granted:

            ActivityCompat.requestPermissions(
                activity,
                [permission],
                1001
            )

            return {
                "error":
                "Location permission requested. "
                "Please tap the button again."
            }

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
                "error":
                "No location available yet."
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
