# -*- coding: utf-8 -*-


# TaskArena - Adding collaborative functionality to TaskWarrior
# Copyright (C) 2015  Nikolai Nowaczyk
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import json
import uuid
import tasklib.task as tlib
import os.path
import subprocess

uda_config_list = [
    {'uda.Arena.type': 'string'},
    {'uda.Arena.label': 'Arena'},
    {'uda.ArenaTaskID.type': 'numeric'},
    {'uda.ArenaTaskID.label': 'ArenaTaskID'},
]

tw_attrs_editable = [
    'depends',
    'description',
    'due',
    'end',
    'imask',
    'mask',
    'parent',
    'priority',
    'project',
    'recur',
    'scheduled',
    'start',
    'status',
    'tags',
    'until',
    'wait',
]

tw_attrs_special = [
    'annotations',
]

tw_attrs_read_only = [
    'id',
    'entry',
    'urgency',
    'uuid',
    'modified'
]


class SharedTask(object):
    """ A Task that can be shared in an arena."""

    def __init__(self, tw_task, arena=None):
        self.tw_task = tw_task
        self.Arena = arena
        self._ArenaTaskID = None

    def _get_arena(self):
        return self._Arena

    def _set_arena(self, value):
        self._Arena = value
        if value:
            self.tw_task['Arena'] = self.Arena.name
            if not self.ArenaTaskID:
                self.ArenaTaskID = uuid.uuid4().__int__()
        else:
            self.remove()

    Arena = property(_get_arena, _set_arena)

    def _get_arena_task_id(self):
        return self.tw_task['ArenaTaskID']

    def _set_arena_task_id(self, value):
        self.tw_task['ArenaTaskID'] = value

    ArenaTaskID = property(_get_arena_task_id, _set_arena_task_id)

    def remove(self):
        self.tw_task['Arena'] = ''
        self.tw_task['ArenaTaskID'] = ''

    def last_modified(self):
        return self.tw_task['modified'] if self.tw_task['modified'] else self.tw_task['entry']

    def update(self, other):
        for field in tw_attrs_editable:
            if self.tw_task[field] != other.tw_task[field]:
                self.tw_task[field] = other.tw_task[field]

    def different_fields(self, other):
        result = []
        for field in tw_attrs_editable:
            if self.tw_task[field] != other.tw_task[field]:
                result.append(field)
        return result

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.ArenaTaskID == other.ArenaTaskID
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return str({'Arena': self.Arena.name, 'ArenaTaskID:': self.ArenaTaskID, 'tw_task': self.tw_task.__dict__})

    def __str__(self):
        return str(self.__repr__())

    def save(self):
        try:
            self.tw_task.save()
            return 1
        except:
            return 0


class EnhancedTaskWarrior(object):
    def __init__(self, tw, arena):
        self.tw = tw
        self.arena = arena
        for uda in uda_config_list:
            self.tw.config.update(uda)

    def tasks(self, pattern):
        return [SharedTask(task, self.arena) for task in
                self.tw.tasks.filter(' '.join(pattern))]

    def add_task(self, task):
        t = SharedTask(tlib.Task(self.tw), self.arena)
        for field in tw_attrs_editable:
            t.tw_task[field] = task.tw_task[field]
        return t


class TaskArena(object):
    """ A project that is shared with others. """

    def __init__(self, arena_name='', ldata='/', rdata='/'):
        self._local_data = None
        self._remote_data = None
        self.tw_local = None
        self.tw_remote = None
        self.name = arena_name
        self.local_data = ldata
        self.remote_data = rdata
        self.SyncManager = SyncManager(self)

    def get_local_data(self):
        return self._local_data

    def set_local_data(self, ldata):
        self._local_data = ldata
        self.tw_local = EnhancedTaskWarrior(tlib.TaskWarrior(data_location=ldata), self)

    local_data = property(get_local_data, set_local_data)

    def get_remote_data(self):
        return self._remote_data

    def set_remote_data(self, rdata):
        self._remote_data = rdata
        self.tw_remote = EnhancedTaskWarrior(tlib.TaskWarrior(data_location=rdata), self)

    remote_data = property(get_remote_data, set_remote_data)

    def get_json(self):
        return self.__repr__()

    def set_json(self, data):
        self.name = data['name']
        self.local_data = data['local_data']
        self.remote_data = data['remote_data']

    json = property(get_json, set_json)

    def __repr__(self):
        return {'name': self.name, 'local_data': self.local_data, 'remote_data': self.remote_data}

    def __str__(self):
        return str(self.__repr__())

    def add(self, pattern):
        tasks = self.tw_local.tasks(pattern)
        for ta_task in tasks:
            ta_task.save()
        return tasks

    def remove(self, pattern):
        tasks = self.tw_local.tasks([pattern, 'Arena:' + self.name])
        for ta_task in tasks:
            ta_task.remove()
            ta_task.save()
        return tasks

    def sync(self):
        self.SyncManager.generate_synclist()
        self.SyncManager.suggest_conflict_resolution()
        self.SyncManager.let_user_check_and_modify_synclist()
        self.SyncManager.carry_out_sync()


class SyncManager(object):
    def __init__(self, arena):
        self.arena = arena
        self.synclist = []

    @property
    def synclist_not_skipped(self):
        return [e for e in self.synclist if e.suggestion != 'SKIP']

    def generate_synclist(self):
        local_tasks = self.arena.tw_local.tasks('')
        remote_tasks = self.arena.tw_remote.tasks('')
        for ltask in local_tasks:
            rtask = next((t for t in remote_tasks if t == ltask), None)
            if rtask:
                self.synclist.append(SyncElement(ltask, rtask, ltask.different_fields(rtask), 'CONFLICT'))
            else:
                self.synclist.append(SyncElement(ltask, None, None, 'UPLOAD'))
        for rtask in remote_tasks:
            if rtask not in local_tasks:
                self.synclist.append(SyncElement(None, rtask, None, 'DOWNLOAD'))

    def suggest_conflict_resolution(self):
        simplified_synclist = []
        for e in self.synclist:
            if e.suggestion == 'CONFLICT':
                if e.fields:
                    if e.local_task.last_modified() >= e.remote_task.last_modified():
                        e.suggestion = 'UPLOAD'
                    else:
                        e.suggestion = 'DOWNLOAD'
                    simplified_synclist.append(e)
            else:
                simplified_synclist.append(e)
        self.synclist = simplified_synclist

    def let_user_check_and_modify_synclist(self):
        if self.synclist:
            self.arena.IOManager.send_message("Suggesting the following sync operations on " + self.arena.name + "...",
                                              1, 2)
            sync_command = self.arena.IOManager.sync_preview(self.synclist)
            if sync_command == 'a':
                for elem in self.synclist:
                    elem.action = elem.suggestion
            elif sync_command == 'm':
                self.arena.IOManager.send_message("Starting manual sync...", 1, 1)
                for elem in self.synclist:
                    self.arena.IOManager.print_separator()
                    sc = self.arena.IOManager.sync_choice(elem)
                    if sc == 'u':
                        elem.action = 'UPLOAD'
                        self.arena.IOManager.send_message("Task uploaded.", 1)
                    elif sc == 'd':
                        elem.action = 'DOWNLOAD'
                        self.arena.IOManager.send_message("Task downloaded.", 1)
                    elif sc == 's':
                        elem.action = 'SKIP'
                        self.arena.IOManager.send_message("Task skipped.", 1)
                    elif sc == 'c':
                        self.arena.IOManager.send_message("Sync canceled.", 0, 1)
                        self.synclist = []
                        break
        else:
            self.arena.IOManager.send_message("Arena " + self.arena.name + " is in sync.")

    def carry_out_sync(self):
        for elem in self.synclist:
            if elem.action == 'UPLOAD':
                if elem.remote_task:
                    elem.remote_task.update(elem.local_task)
                else:
                    elem.remote_task = self.arena.tw_remote.add_task(elem.local_task)
                    elem.remote_task.ArenaTaskID = elem.local_task.ArenaTaskID
                elem.remote_task.save()
            elif elem.action == 'DOWNLOAD':
                if elem.local_task:
                    elem.local_task.update(elem.remote_task)
                else:
                    elem.local_task = self.arena.tw_local.add_task(elem.remote_task)
                    elem.local_task.ArenaTaskID = elem.remote_task.ArenaTaskID
                elem.local_task.save()
        if self.synclist:
            self.arena.IOManager.send_message("Sync complete.", 1, 1)

    def __repr__(self):
        return str({'arena:': self.arena.__str__(),
                    'synclist:': [e.__str__() for e in self.synclist]})

    def __str__(self):
        return str({'arena:': self.arena.__str__(),
                    'synclist:': [e.__str__() for e in self.synclist]})


class SyncElement(object):
    def __init__(self, ltask=None, rtask=None, fields=None, suggestion='', action=''):
        self.local_task = ltask
        self.remote_task = rtask
        self.suggestion = suggestion
        self.action = action
        self.fields = fields

    @property
    def local_description(self):
        return self.local_task.tw_task['description'] if self.local_task else ''

    @property
    def remote_description(self):
        return self.remote_task.tw_task['description'] if self.remote_task else ''

    @property
    def local_last_modified(self):
        return str(self.local_task.last_modified()) if self.local_task else ''

    @property
    def remote_last_modified(self):
        return str(self.remote_task.last_modified()) if self.remote_task else ''

    def __repr__(self):
        return {'local_task': self.local_task.__repr__(),
                'remote_task:': self.remote_task.__repr__(),
                'suggestion:': self.suggestion,
                'action:': self.action,
                'fields:': self.fields}

    def __str__(self):
        return str({'local_task': self.local_task,
                    'remote_task:': self.remote_task,
                    'suggestion:': self.suggestion,
                    'action:': self.action,
                    'fields:': self.fields})


class IOManager(object):
    def __init__(self, show_output=True, seplength=75, te=None):
        self.show_output = show_output
        self.seplength = seplength
        self.TaskEmperor = te

    @staticmethod
    def formatted_print(t):
        print("{0:6}   {1:25}   {2:20}   {3:10}\n".format(t[0][0:6], t[1][0:25], t[2][0:20], t[3][0:10]))

    @staticmethod
    def newlines(num):
        if num:
            print("\n" * (num - 1))

    @staticmethod
    def get_input(msg, pre_blanks=0, post_blanks=0):
        print("\n" * pre_blanks)
        data = raw_input(msg)
        print("\n" * post_blanks)
        return data

    @staticmethod
    def execute_command(command_args):
        p = subprocess.Popen(command_args,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        p.communicate(input='y\n')

    def process_commands(self, args):
        if args.command:
            configfile = os.path.expanduser("~") + "\\task_arena_config"
            self.TaskEmperor = TaskEmperor(configfile)
            if args.command == 'install':
                for uda in uda_config_list:
                    IOManager.execute_command(['task', 'config', uda.keys()[0], uda[uda.keys()[0]]])
                self.send_message("TaskArena installed.")
            elif args.command == 'uninstall':
                for uda in reversed(uda_config_list):
                    IOManager.execute_command(['task', 'config', uda.keys()[0]])
                os.remove(configfile)
                self.send_message("TaskArena uninstalled.")
            elif args.command == 'create':
                self.send_message("Creating new Arena...")
                name = self.get_input('Enter a name: ')
                ldata = self.get_input('Enter local data.location: ')
                rdata = self.get_input('Enter remote data.location: ')
                self.TaskEmperor.create_arena(name, ldata, rdata)
                self.TaskEmperor.save()
            elif args.command == 'list':
                if self.TaskEmperor.arenas:
                    self.send_message("The following arenas are available:", 1, 1)
                    for arena in self.TaskEmperor.arenas:
                        self.send_message("arena : " + arena.name)
                        self.send_message("local : " + arena.local_data)
                        self.send_message("remote: " + arena.remote_data)
            elif args.command in ['add', 'remove', 'delete', 'sync']:
                if args.arena:
                    arena = self.TaskEmperor.find(args.arena)
                    if arena:
                        if args.command == 'add':
                            arena.add(args.filter)
                            self.send_message("Tasks added.")
                        elif args.command == 'remove':
                            arena.remove(args.filter)
                            self.send_message("Tasks removed from " + arena.name + " .")
                        elif args.command == 'delete':
                            self.TaskEmperor.delete_arena(arena)
                        elif args.command == 'sync':
                            arena.sync()
                    else:
                        self.send_message("Arena " + args.arena + " not found.")
                else:
                    self.send_message("You must supply an ArenaTaskID.")
        else:
            self.send_message("No command supplied.")


    def send_message(self, msg, pre_blanks=0, post_blanks=0):
        if self.show_output:
            IOManager.newlines(pre_blanks)
            print(msg)
            IOManager.newlines(post_blanks)

    def print_separator(self):
        self.send_message("-" * self.seplength)

    def sync_preview(self, synclist):
        self.print_separator()
        IOManager.formatted_print(('', 'Task', 'LastModified', 'Suggestion'))
        self.print_separator()
        for e in synclist:
            IOManager.formatted_print(('Local', e.local_description, e.local_last_modified, ''))
            IOManager.formatted_print(('Remote', e.remote_description, e.remote_last_modified, e.suggestion))
            self.print_separator()
        return IOManager.get_input("Do you want to sync (a)ll, sync (m)anually or (c)ancel? (a/m/c) ", 1)

    def sync_choice(self, e):
        if e.local_task:
            self.send_message("Task Description: " + e.local_task.tw_task['description'])
            self.send_message("ArenaTaskID     : " + e.local_task.ArenaTaskID)
            if e.remote_task:
                self.send_message("Task exists in both repositories.", 1, 1)
                self.send_message("Last modified (local) : " + e.local_last_modified)
                self.send_message("Last modified (remote): " + e.remote_last_modified)
                self.send_message("Suggesting to " + e.suggestion + ".", 1, 1)
                self.send_message("This would cause the following modifications:", 0, 1)
                for field in e.fields:
                    local_field = str(e.local_task.tw_task[field]) if e.local_task.tw_task[field] else '(empty)'
                    remote_field = str(e.remote_task.tw_task[field]) if e.remote_task.tw_task[field] else '(empty)'
                    self.send_message(field + ": " + local_field + (
                        " -> " if e.suggestion == 'UPLOAD' else ' <- ') + remote_field)
                result = IOManager.get_input("Do you want to (u)pload, (d)ownload, (s)kip or (c)ancel sync? (u/d/s/c) ",
                                             1)
            else:
                self.send_message("This task does not yet exist on remote. Suggestion: " + e.suggestion, 1)
                result = IOManager.get_input("Do you want to (u)pload, (s)kip or (c)ancel sync? (u/s/c) ", 1)
        else:
            self.print_separator()
            self.send_message("Description: " + e.remote_task.tw_task['description'])
            self.send_message("ArenaTaskID: " + e.remote_task.ArenaTaskID)
            self.send_message("This task does not yet exist on local.", 1)
            result = IOManager.get_input("Do you want to (d)ownload, (s)kip or (c)ancel sync? (d/s/c) ", 1)
        return result


class TaskEmperor(object):
    """ A class to handle all your TaskArenas """

    def __init__(self, configfile='', output=True):
        self.arenas = []
        self.IOManager = IOManager(output)
        self.configfile = configfile

    def _get_configfile(self):
        return self._configfile

    def _set_configfile(self, value):
        if value:
            self._configfile = value
            self.load()

    configfile = property(_get_configfile, _set_configfile)

    def load(self):
        if os.path.isfile(self.configfile):
            f = open(self.configfile)
            try:
                self.json = json.load(f)
                self.IOManager.send_message("Arenas loaded.")
            except:
                self.IOManager.send_message("Warning: Config file " + self.configfile + " is empty or corrupt.")
        else:
            open(self.configfile, 'w+')
            self.IOManager.send_message("New arena config created at " + self.configfile)

    def save(self):
        f = open(self.configfile, 'w+')
        json.dump(self.json, f)
        self.IOManager.send_message("TaskEmperor saved.")

    def get_json(self):
        return {'arenas': [p.json for p in self.arenas]}

    def set_json(self, data):
        self.arenas = []
        for json_project in data['arenas']:
            arena = TaskArena()
            arena.json = json_project
            arena.IOManager = self.IOManager
            self.arenas.append(arena)

    json = property(get_json, set_json)

    def __repr__(self):
        return {'configfile': self.configfile,
                'arenas': [p.__repr__() for p in self.arenas]}

    def __str__(self):
        return str(self.__repr__())

    def create_arena(self, arena_id, ldata, rdata):
        arena = None
        if arena_id in [p.name for p in self.arenas]:
            self.IOManager.send_message("Arena " + arena_id + " already exists!")
        else:
            arena = TaskArena(arena_id, ldata, rdata, self.IOManager)
            self.arenas.append(arena)
            self.IOManager.send_message("Arena " + arena.name + " created.")
        return arena

    def delete_arena(self, arena):
        arena.remove('')
        self.arenas.remove(arena)
        self.save()
        self.IOManager.send_message("Arena " + arena.name + " deleted.")

    def find(self, arena_name):
        for arena in self.arenas:
            if arena.name == arena_name:
                return arena