# zoom-attendance-plotter
Plot data from Zoom meeting and chat records.

### Setting things up:

1. Install numpy, pandas, and matplotlib.  
The easiest way to do this is to install Anaconda, which you may have already done.

1. Locate the directory where Zoom stores meeting information.  
The location of this directory is something you configure in Zoom.
It will have a subdirectory for each meeting.  Make sure to configure 
Zoom to save chat data.  

1. For each class you teach, create a roster file in the Zoom directory
containing the names of students in the class.  The name of the file has 
to correspond to the name of your Zoom meeting for the class.  For example, 
I have a "OS.csv" file because OS is the name of my OS class meetings.

1. Make sure attendance.py is in your PATH.

Here are the first few lines of an example roster file:

    First name,Last name,alias
    Armon,Factor,
    Lesley,Busann,Les Busann
    Ana,Perez,

The alias column gives alternative names that might appear in the Zoom data.

### Creating plots:

1.  After class meets, download a meeting report on zoom.us and store it in the Zoom directory 
for that zoom meeting.  Don't change the file name.

1.  Call the attendance.py with the zoom directory name, course name,date, and start/end times.
For example:

attendance.py "/mnt/c/CSUMB/Spring21/video/" "OS" "2021-02-03" "10:00:00 AM" "11:50:00 AM"

