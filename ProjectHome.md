If for some reason you have a number of abandoned pickle files (e.g. a doomed web app originally stored user info this way), this script can help you recover your data without spending the 10 minutes it would take to write the script yourself.

Given a Python pickle file (text or binary), this script translates the original file to any of the following text-based, human-readable formats:
  * Plain, unformatted text
  * repr() (Python code representation)
  * JSON
  * XML
  * DataTree

And a few more formats are goals, but not yet implemented:
  * ReStructured Text
  * YAML

Note that some of these formats currently require that the library for the target format is available. The dependencies all have free implementations, so for the sake of making this script more immediately useful, I'll eventually include the necessary code from those sources in this script.