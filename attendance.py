#!/usr/bin/env python3

"""

Plot attendance from Zoom files.

Three files are used:
    - zoom chat file (found in the directory for a single zoom meeting)
    - zoom participation file (downloaded from zoom.us and put in directory for meeting)
    - class roster file (parent directory of all zoom meeting directories)
      This file has three columns: "First name", "Last name", "alias"
      The alias column describes an alias for the combination of first name
      and last name.  For example, a row might contain 'Steven,Smith,Steve Smith'.
      Currently only a single alias is supported.
    
Author: Glenn Bruns

"""

"""

To do:
    - add main program through which command-line parameters can be provided
    - support a single-student plot, where each line is a day

"""

import re
from pathlib import Path
from argparse import ArgumentParser 
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pandas.plotting import register_matplotlib_converters

sns.set(style='white')
sns.set_context('notebook') 
register_matplotlib_converters  

# parameters

grace_minutes = 2
min_duration = 0.9
max_unanswered = 1

def read_participation(participation_file):
    """ Return data frame with meeting join/leave data. """
    
    df = pd.read_csv(participation_file)
    df.columns = ['name', 'email', 'join', 'leave', 'duration', 'guest']
    
    # remove part of name in parentheses
    df['name'] = df['name'].str.replace(' \(.*\)', '')
    
    # convert join, leave times to Pandas timestamps
    df['join']  = pd.to_datetime(df['join'])
    df['leave'] = pd.to_datetime(df['leave'])
    
    return df


def read_chat(chat_file, meeting_date):
    """ Return data frame with user name and chat time. """
    tbl = []
    for line in open(chat_file, encoding='utf8'):
        # validate the line
        if not (" " in line and " : " in line and line[:1].isnumeric()):
            continue
        
        private = 'Direct' in line
        time = line.split()[0]
        date = meeting_date + ' ' + time
        if private:
            name = (line.split(' From ')[1].split(' to ')[0]).strip()
        else:
            name = (line.split(' From ')[1].split(':')[0]).strip()
        name = re.sub(' \(.*\)', '', name)  # remove nickname
        tbl.append([name, date, private])
        
    df = pd.DataFrame(tbl, columns=['name', 'date', 'private'])
    df['date'] = pd.to_datetime(df['date'])
    
    return df


def read_roster(roster_file):
    """ Return student names and alias dictionary from roster file. """
    
    df = pd.read_csv(roster_file)
    names = df['First name']+' '+df['Last name'] 
    
    df['alias'].fillna('', inplace=True)  # '' or NA indicates no alias
    alias = df['alias']
    mask = (df['alias'] != '')
    aliases = dict(zip(alias[mask], names[mask]))

    return names, aliases    


def find_question_periods(chat, k=10, window_size='45s'):
    """ From chat data, find periods in which students are answering questions. 
    
    A question-answering period is a maximally-long period that begins with
    a private chat, has no window within it with no private
    chats, and has some window within it with at least k private chats.
    
    45 seconds seems to be a good default window size, but probably a
    slightly smaller one would work just as well.  The issue is with
    back-to-back questions.
        
    Note that the Pandas rolling window algorithm uses the right-edge
    time as the time for a window, and does not record zero counts.
    So the window moves forward in time until it captures the first
    event, then records a count of one.  It moves right again until
    it captures the next even, and then records a count of how many
    events are now in the window (which would be 1 or 2).  """
    
    cp = chat[chat['private'] == True]
    cp.set_index('date', inplace=True)
    cp.sort_index(inplace=True)    
    
    # note that the times in cp are times for the right edges of
    # the window
    cpr = cp.rolling(window_size).sum()    
    
    # this can be used to plot the question answering activity
    # plt.plot(cpr)
    
    max_count = 0
    start_time = None
    end_time = None
    periods = []
    for i in range(cpr.shape[0]):
        t = cpr.index[i]
        count = cpr['private'][i]
        if count == 1:
            # wrap up previous period, if any
            if max_count > k:
                periods.append([start_time, end_time, max_count])
                
            # start new period
            start_time = t
            end_time = None
            max_count = 1
        else:
            # count > 1; extend current period
            end_time = t
            if count > max_count:
                max_count = count
    
    # wrap up previous period, if any
    if max_count > k:
        periods.append([start_time, end_time, max_count])

    df = pd.DataFrame(periods)
    if df.size > 0:
        df.columns = ['start', 'end', 'max_count']  

    return df    


def students_without_answer(chat, start, end, names):
    """ Return a list of students who did not send a private chat
        between times start and end. """
        
    answered = chat[(chat['date'] >= start) & (chat['date'] <= end)]['name'].unique()
    unanswered = list(set(names) - set(answered))
    return unanswered


def make_attendance_plot(zoom_dir, course, meeting_date, classtime, outfile_name='attendance.png'):
    """ Read Zoom meeting data, Zoom chat data, course roster, and generate attendance plot. """

    #
    # locate zoom directory and data files
    #
    
    meeting_dir = list(Path(zoom_dir).glob('*'+meeting_date+'*'+course+'*'))
    if len(meeting_dir) != 1:
        raise SystemExit('error: not exactly 1 zoom meeting for {} on date {}'.format(course, meeting_date))
    else:
        meeting_dir = meeting_dir[0]
        
    roster_file = list(Path(zoom_dir).glob(course+'*.csv'))
    if len(roster_file) != 1:
        raise SystemExit('error: No file {}*.csv in {}'.format(course, zoom_dir))
    else:
        roster_file = roster_file[0]
    
    participation_file = list(meeting_dir.glob('participants*.csv'))
    if len(participation_file) != 1:
        raise SystemExit('error: not exactly 1 participation file in {}'.format(meeting_dir))
    else:
        participation_file = participation_file[0]
        
    chat_file = list(meeting_dir.glob('chat.txt'))
    if len(chat_file) != 1:
        raise SystemExit('error: not exactly 1 chat file in {}'.format(meeting_dir))
    else:
        chat_file = chat_file[0]
        
    #
    # read and process the data
    #
    
    # get lecture start and end times
    start_time = pd.to_datetime(meeting_date+' '+classtime[0])
    end_time   = pd.to_datetime(meeting_date+' '+classtime[1])
    class_len_mins = pd.Timedelta(end_time - start_time)/pd.Timedelta(minutes=1)
    
    # read roster, participation (join/leave), and chat data
    roster, aliases = read_roster(roster_file)
    df = read_participation(participation_file)
    chat = read_chat(chat_file, meeting_date)
    
    # remove any aliases
    df['name'].replace(aliases, inplace=True)
    chat['name'].replace(aliases, inplace=True)
    
    # report unknown names
    # is any of these besides instructors and TA, need to
    # add to roster file as aliases
    unknown_names = list(set(df['name']) - set(roster))
    print('Unknown names: {}'.format(unknown_names))
    
    # create data frame of names, each with a unique ID
    names = pd.DataFrame({'name': roster})
    names.sort_values(['name'], inplace=True, ascending=False)
    names['id'] = range(names.shape[0])
    
    # add student IDs to join/leave data
    df = df.merge(names, on='name')
    
    # create summary dataframe; add IDs
    summary = pd.DataFrame({'name': roster})
    summary = summary.merge(names, on='name')
    
    #
    # number of minutes in class
    #
    
    # for student, compute total duration
    duration_by_student = df.groupby('name')['duration'].sum().reset_index()
    duration_by_student['frac_duration'] = duration_by_student['duration']/class_len_mins
    
    # add duration info to summary
    summary = summary.merge(duration_by_student, how='left', on='name')
    summary.fillna(0)
    
    #
    # is late to class?
    #
    
    # for each student who joined, get earliest join time
    late_time = start_time + pd.to_timedelta(grace_minutes, unit='minute')
    first_join = df.groupby('name')['join'].min()
    first_join = first_join.reset_index()
    first_join.columns = ['name', 'first_join']
    first_join['is_late'] = first_join['first_join'] > late_time
    
    # add is_late to join/leave and summary
    df = df.merge(first_join[['name', 'is_late']], how='left', on='name')
    summary = summary.merge(first_join[['name', 'is_late']], how='left', on='name')
    
    #
    # joined meeting at all?
    #
    
    # add a column to summary about whether joined
    summary['joined'] = ~summary['is_late'].isna()
    summary['is_late'].fillna(False, inplace=True)
    
    #
    # answered questions?
    #
    
    # compute info on unanswered questions
    all_unanswered = []
    periods = find_question_periods(chat)
    num_questions = periods.shape[0]
    for i in range(num_questions):
        p = periods.iloc[i]
        all_unanswered.extend(students_without_answer(chat, p['start'], p['end'], df['name'].unique()))
    unanswered_counts = pd.Series(all_unanswered).value_counts()
    unanswered_counts = unanswered_counts.rename_axis('name').reset_index(name='num_unanswered')
    unanswered_counts['fraction_unanswered'] = unanswered_counts['num_unanswered']/num_questions
    
    # add columns to summary about missed questions
    summary = summary.merge(unanswered_counts, how='left', on='name')
    summary.fillna(0, inplace=True)
    
    #
    # is absent?  (based on above factors)
    #
    
    # compute is_absent column in summary
    summary['is_absent'] = summary['is_late'] | ~summary['joined'] | (summary['num_unanswered'] > max_unanswered) | (summary['frac_duration'] < min_duration)
    df = df.merge(summary[['name', 'is_absent']], on='name')
    
    #
    # create the plot and write to file
    #
    
    generate_plot(course, df, names, summary, chat, periods, 
                  start_time, end_time, late_time, 
                  meeting_dir / outfile_name)
    
    return summary


def generate_plot(course, df, names, summary, chat, periods, start_time, end_time, late_time, outfile):
    """ Plot attendance and save plot to file.
        green lines: start/end of class
        yellow line: end of grace period after start of class
        cyan lines: question answering periods
        red dots: no answer from student during question answering period """

    # figure has two plots: names in left plot, data on right plot
    fig, ax = plt.subplots(1, 2, figsize=(14,12), sharey=True, 
                           gridspec_kw={'width_ratios': [1, 6], 'wspace':0.15})
    
    # plot start/end times and late time
    ax[1].vlines(x=[start_time, end_time], ymin=0, ymax=len(names)-1, color='black')
    ax[1].vlines(x=[late_time], ymin=0, ymax=len(names)-1, color='orange')
    
    # plot join and leave for each student
    ax[1].hlines(y=df['id'], xmin=df['join'], xmax=df['leave'], color='darkgrey')
    df_late = df[df['is_late']]
    ax[1].hlines(y=df_late['id'], xmin=df_late['join'], xmax=df_late['leave'], color='red')
    
    # plot names
    for i in range(names.shape[0]):
        ax[0].annotate(names.iloc[i]['name'], (0, names.iloc[i]['id']-0.2), annotation_clip=True)
    absent = summary[summary['is_absent']]
    for i in range(absent.shape[0]):
        ax[0].text(0, absent.iloc[i]['id']-0.2, absent.iloc[i]['name'], color='red')
    
    # title and date format on right
    ax[1].set_title('{} Attendance, {}/{}'.format(course, start_time.month, start_time.day))
    # use only hour/minute in x tick labels
    xfmt = mdates.DateFormatter('%H:%M')
    ax[1].xaxis.set_major_formatter(xfmt)  
    
    # no tick labels or grid on left
    ax[0].set_xticklabels([]);
    ax[0].set_yticklabels([]);
    ax[0].grid(False)
    for spine in ['left', 'right', 'top', 'bottom']:
        ax[0].spines[spine].set_visible(False)
        
    # plot questions intervals and students who didn't answer
    for i in range(periods.shape[0]):
        p = periods.iloc[i]
        unanswered = students_without_answer(chat, p['start'], p['end'], df['name'].unique())
    
        ax[1].vlines(x=p['start'], ymin=0, ymax=len(names)-1, color='dodgerblue')
        ax[1].vlines(x=p['end'],   ymin=0, ymax=len(names)-1, color='dodgerblue')
        
        # plot unanswered questions
        midp = p['start'] + (p['end']-p['start'])/2
    
        df1 = pd.DataFrame({'name': unanswered})
        df1 = df1.merge(names)
        for j in range(df1.shape[0]):
            ax[1].plot(midp, df1.iloc[j]['id'], 'or')
    
    fig.savefig(outfile)

def main():
    
    # parse command-line arguments
    parser = ArgumentParser(description="Generate a participation plot")
    parser.add_argument("zoom_dir",    help="zoom directory")
    parser.add_argument("course",      help="name of the course")
    parser.add_argument("meeting_date",help="date of the course meeting")
    parser.add_argument("start_time",  help="course start time")
    parser.add_argument("end_time",    help="course end time")
    args = parser.parse_args()
    
    make_attendance_plot(args.zoom_dir, args.course, 
                 args.meeting_date, [args.start_time, args.end_time])
    
def test():
    
    zoom_dir = "C:/Users/Glenn/Google Drive/CSUMB/Spring21/video/"
    course = "Data Science"       
    meeting_date = '2021-02-09'
 
    if course == "OS":
        start_time = '10:00:00 AM'  
        end_time =   '11:50:00 AM' 
    elif course == "Data Science":
        start_time = '02:00:00 PM' 
        end_time =   '03:50:00 PM'
    elif course == "Logic":
        start_time = '10:00:00 AM'
        end_time =   '11:20:00 AM'
    else:
        raise SystemExit('error: No course {}'.format(course))

    
    make_attendance_plot(zoom_dir, course, meeting_date, [start_time, end_time])    
    

if __name__ == '__main__':
    main()
