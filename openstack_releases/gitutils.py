# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import os.path
import subprocess

from openstack_releases import links

# Disable warnings about insecure connections.
from requests.packages import urllib3
urllib3.disable_warnings()


CGIT_SHA_TEMPLATE = 'http://git.openstack.org/cgit/%s/commit/?id=%s'
CGIT_TAG_TEMPLATE = 'http://git.openstack.org/cgit/%s/tag/?h=%s'


def find_modified_deliverable_files():
    "Return a list of files modified by the most recent commit."
    results = subprocess.check_output(
        ['git', 'diff', '--name-only', '--pretty=format:', 'HEAD^']
    ).decode('utf-8')
    filenames = [
        l.strip()
        for l in results.splitlines()
        if l.startswith('deliverables/')
    ]
    return filenames


def commit_exists(workdir, repo, ref):
    """Return boolean specifying whether the reference exists in the repository.

    The commit must have been merged into the repository, but this
    check does not enforce any branch membership.

    """
    try:
        subprocess.check_output(
            ['git', 'show', ref],
            cwd=os.path.join(workdir, repo),
        ).decode('utf-8')
    except subprocess.CalledProcessError as err:
        print('Could not find {}: {}'.format(ref, err))
        return False
    return True


def tag_exists(repo, ref):
    """Return boolean specifying whether the reference exists in the repository.

    Uses a cgit query instead of looking locally to avoid cloning a
    repository or having Depends-On settings in a commit message allow
    someone to fool the check.

    """
    url = CGIT_TAG_TEMPLATE % (repo, ref)
    return links.link_exists(url)


def clone_repo(workdir, repo, ref=None):
    "Check out the code."
    dest = os.path.join(workdir, repo)
    if not os.path.exists(dest):
        cmd = [
            'zuul-cloner',
            '--workspace', workdir,
        ]
        cache_dir = os.environ.get('ZUUL_CACHE_DIR', '/opt/git')
        if cache_dir and os.path.exists(cache_dir):
            cmd.extend(['--cache-dir', cache_dir])
        cmd.extend([
            'git://git.openstack.org',
            repo,
        ])
        subprocess.check_call(cmd)
        # Force an update, just in case the local version is still out of
        # date.
        print('Updating newly cloned repository in %s' % dest)
        subprocess.check_call(
            ['git', 'fetch', '-v', '--tags'],
            cwd=dest,
        )
    # If we were given some sort of reference, check that out.
    if ref:
        print('Updating %s to %s' % (repo, ref))
        subprocess.check_call(
            ['git', 'checkout', ref],
            cwd=dest,
        )


def sha_for_tag(workdir, repo, version):
    """Return the SHA for a given tag
    """
    # git log 2.3.11 -n 1 --pretty=format:%H
    try:
        actual_sha = subprocess.check_output(
            ['git', 'log', str(version), '-n', '1', '--pretty=format:%H'],
            cwd=os.path.join(workdir, repo),
            stderr=subprocess.STDOUT,
        ).decode('utf-8')
        actual_sha = actual_sha.strip()
    except subprocess.CalledProcessError as e:
        print('ERROR getting SHA for tag %r: %s [%s]' %
              (version, e, e.output.strip()))
        actual_sha = ''
    return actual_sha


def _filter_branches(output):
    "Strip garbage from branch list output"
    return [
        n
        for n in output.strip().split()
        if '/' in n or n == 'master'
    ]


def stable_branch_exists(workdir, repo, series):
    "Does the stable/series branch exist?"
    remote_match = 'remotes/origin/stable/%s' % series
    try:
        containing_branches = _filter_branches(
            subprocess.check_output(
                ['git', 'branch', '-a'],
                cwd=os.path.join(workdir, repo),
            ).decode('utf-8')
        )
        return (remote_match in containing_branches)
    except subprocess.CalledProcessError as e:
        print('ERROR checking for branch: %s [%s]' % (e, e.output.strip()))
        return False


def check_branch_sha(workdir, repo, series, sha):
    """Check if the SHA is in the targeted branch.

    The SHA must appear on a stable/$series branch (if it exists) or
    master (if stable/$series does not exist). It is up to the
    reviewer to verify that releases from master are in a sensible
    location relative to other existing branches.

    We do not compare $series against the existing branches ordering
    because that would prevent us from retroactively creating a stable
    branch for a project after a later stable branch is created (i.e.,
    if stable/N exists we could not create stable/N-1).

    """
    remote_match = 'remotes/origin/stable/%s' % series
    try:
        containing_branches = _filter_branches(
            subprocess.check_output(
                ['git', 'branch', '-a', '--contains', sha],
                cwd=os.path.join(workdir, repo),
            ).decode('utf-8')
        )
        # If the patch is on the named branch, everything is fine.
        if remote_match in containing_branches:
            return True
        # If the expected branch does not exist yet, this may be a
        # late release attempt to create that branch or just a project
        # that hasn't branched, yet, and is releasing from master for
        # that series. Allow the release, as long as it is on the
        # master branch.
        all_branches = _filter_branches(
            subprocess.check_output(
                ['git', 'branch', '-a'],
                cwd=os.path.join(workdir, repo),
            ).decode('utf-8')
        )
        if (remote_match not in all_branches) and ('master' in containing_branches):
            return True
        # At this point we know the release is not from the required
        # branch and it is not from master, which means it is the
        # wrong branch and should not be allowed.
        return False
    except subprocess.CalledProcessError as e:
        print('ERROR checking SHA on branch: %s [%s]' % (e, e.output.strip()))
        return False


def check_ancestry(workdir, repo, old_version, sha):
    "Check if the SHA is in the ancestry of the previous version."
    try:
        ancestors = subprocess.check_output(
            ['git', 'log', '--oneline', '--ancestry-path',
             '%s..%s' % (old_version, sha)],
            cwd=os.path.join(workdir, repo),
        ).decode('utf-8').strip()
        return bool(ancestors)
    except subprocess.CalledProcessError as e:
        print('ERROR checking ancestry: %s [%s]' % (e, e.output.strip()))
        return False


def get_latest_tag(workdir, repo, sha=None):
    cmd = ['git', 'describe', '--abbrev=0', '--always']
    if sha is not None:
        cmd.append(sha)
    try:
        return subprocess.check_output(
            cmd,
            cwd=os.path.join(workdir, repo),
            stderr=subprocess.STDOUT,
        ).decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        print('WARNING failed to retrieve latest tag: %s [%s]' %
              (e, e.output.strip()))
        return None


def get_branches(workdir, repo):
    try:
        output = subprocess.check_output(
            ['git', 'branch', '-a'],
            cwd=os.path.join(workdir, repo),
            stderr=subprocess.STDOUT,
        ).decode('utf-8').strip()
        # Example output:
        # * (no branch)
        #   master
        #   stable/mitaka
        #   stable/newton
        #   stable/ocata
        #   remotes/origin/HEAD -> origin/master
        #   remotes/origin/master
        #   remotes/origin/stable/mitaka
        #   remotes/origin/stable/newton
        #   remotes/origin/stable/ocata
        results = []
        for line in output.splitlines():
            branch = line.strip().lstrip('*').strip()
            if branch.startswith('('):
                continue
            if '->' in branch:
                continue
            results.append(branch)
        return results
    except subprocess.CalledProcessError as e:
        print('ERROR failed to retrieve list of branches: %s [%s]' %
              (e, e.output.strip()))
        return []


def branches_containing(workdir, repo, ref):
    try:
        output = subprocess.check_output(
            ['git', 'branch', '-r', '--contains', ref],
            cwd=os.path.join(workdir, repo),
            stderr=subprocess.STDOUT,
        ).decode('utf-8').strip()
        # Example output:
        #   origin/stable/ocata
        results = []
        for line in output.splitlines():
            results.append(line.strip())
        return results
    except subprocess.CalledProcessError as e:
        print('ERROR failed to retrieve list of branches containing %s: %s [%s]' %
              (ref, e, e.output.strip()))
        return []


def get_branch_base(workdir, repo, branch):
    "Return SHA at base of branch."
    # http://stackoverflow.com/questions/1527234/finding-a-branch-point-with-git
    # git rev-list $(git rev-list --first-parent ^origin/stable/newton master | tail -n1)^^!
    #
    # Determine the first parent.
    cmd = [
        'git',
        'rev-list',
        '--first-parent',
        '^origin/{}'.format(branch),
        'master',
    ]
    try:
        parents = subprocess.check_output(
            cmd,
            cwd=os.path.join(workdir, repo),
            stderr=subprocess.STDOUT,
        ).decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        print('WARNING failed to retrieve branch base: %s [%s]' %
              (e, e.output.strip()))
        return None
    parent = parents.splitlines()[-1]
    # Now get the ^^! commit
    cmd = [
        'git',
        'rev-list',
        '{}^^!'.format(parent),
    ]
    try:
        return subprocess.check_output(
            cmd,
            cwd=os.path.join(workdir, repo),
            stderr=subprocess.STDOUT,
        ).decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        print('WARNING failed to retrieve branch base: %s [%s]' %
              (e, e.output.strip()))
        return None
