# NetWatch Presentation Script

Simple speaking script, one section per slide. About 8-10 minutes in total.

### Slide 1 - Title

"Good morning everyone. My project is NetWatch, a Real-Time Network Monitoring and Troubleshooting System. It is a Computer Networks project that monitors a real network and shows the results on a live dashboard. I am AKULA AJAY KUMAR."

### Slide 2 - Introduction

"NetWatch is a small web application that runs on a computer. It checks the network again and again and shows if the network is online, how fast it is and where a problem may be. It uses Python, Flask and plain web pages."

### Slide 3 - Real-World Problem

"Suppose the internet becomes slow in a college computer lab. The administrator needs to know whether the problem is with the local network, gateway, DNS, internet connection, or a particular service. NetWatch helps identify these basic problems from one dashboard."

### Slide 4 - Motivation

"Many small networks have no monitoring tool. Professional tools are big and complex. I wanted a simple tool that students and small offices can run in one minute and that also teaches networking concepts like ping, DNS and ports."

### Slide 5 - Objectives

"The objectives are: monitor connectivity in real time, measure latency and packet loss, check the gateway, DNS and services, show bandwidth, raise alerts, keep an event log and give simple troubleshooting help."

### Slide 6 - Proposed Solution

"I built a Flask server with a monitoring engine that runs in the background. It collects real data from the operating system and the network. The browser dashboard reads this data every few seconds."

### Slide 7 - Technology Stack

"Python and Flask for the backend. The Python socket, subprocess and urllib libraries for the checks. psutil for interface statistics. HTML, CSS and JavaScript for the dashboard. No paid services, no API keys."

### Slide 8 - System Architecture

"The browser talks to Flask. Flask reads results from the monitoring engine. The engine uses helper functions that talk to the operating system network stack, which reaches the gateway, the internet and the services we configure."

### Slide 9 - Real-Time Monitoring

"The checks run on different timers. Interface statistics every 2 seconds, gateway every 4, internet and services every 6, and DNS every 10 seconds. This avoids sending too much traffic."

### Slide 10 - Gateway & Internet Monitoring

"NetWatch finds the default gateway from the routing table and pings it. For the internet it pings a public address and makes a small HTTPS request. If the gateway works but the internet does not, the problem may be upstream. If the gateway fails, the local path is the likely problem."

### Slide 11 - DNS & Service Monitoring

"For DNS, NetWatch resolves a domain and shows the IP and response time. For services, it makes one TCP connection to a host and port that the user configured. It never scans ports."

### Slide 12 - Latency & Packet Loss

"Each cycle sends three pings. Latency is the reply time. Packet loss is sent minus received, divided by sent, times one hundred. The graph keeps only the latest samples."

### Slide 13 - Bandwidth Monitoring

"NetWatch reads the bytes sent and received on the selected interface twice and calculates the rate. Speed in Mbps is change in bytes times eight, divided by time, divided by one million. This is the traffic now, not the maximum line speed."

### Slide 14 - Network Troubleshooter

"The user presses Run Network Diagnostics. It tests the interface, gateway, DNS, internet and services in order, and shows PASS or FAIL with a possible cause and suggested steps. It does not claim to find every root cause."

### Slide 15 - Dashboard Screenshots

"These are screenshots from my computer while running the project: the dashboard, the latency graph, the service monitoring and the troubleshooter. (Insert your own screenshots here.)"

### Slide 16 - Testing

"I wrote unit tests for IP detection, interfaces, gateway parsing, ping, DNS, ports, HTTP, bandwidth, packet loss, invalid input, timeouts and failure handling. I also did a live test: stopping and starting a local service made NetWatch show SERVICE DOWN and SERVICE RESTORED. (State your own Windows test results.)"

### Slide 17 - Advantages & Future Scope

"Advantages: simple, free, runs locally, uses real measurements. Future scope: SNMP, multiple devices, a database for history, email or SMS alerts, and Grafana integration."

### Slide 18 - Conclusion

"NetWatch shows how Computer Networks concepts can solve a real problem. It gives an administrator a quick view of network health and a first step for troubleshooting. Thank you. I am ready for your questions."
