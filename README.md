# compile-report-pack - Google Cloud Function Deployment
A fork of [ContrastingSounds/compile-report-pack](https://github.com/ContrastingSounds/compile-report-pack) designed for deployment on Google Cloud Functions

# User Information
Follow normal instructions on parent repo

**Google Cloud specific instructions**
* Deploy `/google_cloud/list/action_list` and * `google_cloud/execute/action_execute/` as separate google cloud functions
  * Allow unauthenticated invocations and deploy as HTTP triggers
  * The root URL of the `/form` and `/execute` function should be used as the URL in the list function (currently marked `REPLACE_ME`)
    * Keep the `/form` and `/execute` paths 
* The `execute` function needs to be deployed with some additional configuration:
  * Set some environment variables on the cloud function as defined in the `env.example` file (replace with real values)
  * Include the `requirements.txt` file in the cloud function

**Looker instructions**
* See parent repo [here](https://github.com/ContrastingSounds/compile-report-pack)