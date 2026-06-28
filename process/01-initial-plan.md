# Initial prompt for Plan mode - Opus 
I want to build an application that read the AIS signals that a USB radio receives. It will be deployed in a raspberry pi and should have the following features:
- Store in a database (an online version, like Supabase) the vessel information stored in the signal. Avoid initiating the process if we received the signal less than 5 minutes ago, to avoid duplicates.
- Retrieve info from the internet about the vessel. What tool should we use? It would be interesting to have an image, size, what is for...
- Send a notification to telegram when a new signal is received. Should be automatic and as quick as possible. Add the information we have about the vessel. Check in the database when was the last time we saw it.
- At the end of the day, send some statistics about the signals we recieved that day.
- At the end of the week, send statistics of the signals received that week.

In terms of code, the system should be ready to change the input of the data (the usb radio) with something else.

What other features we could have?

# Built with Sonnet 3.5
# Used skill Grill me to find improvements