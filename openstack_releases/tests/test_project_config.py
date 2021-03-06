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

from oslotest import base

from openstack_releases import project_config


class TestReleaseJobsStandard(base.BaseTestCase):

    def test_no_artifact_flag(self):
        deliverable_info = {
            'repository-settings': {
                'openstack/releases': {
                    'flags': [
                        'no-artifact-build-job',
                    ],
                },
            },
        }
        zuul_layout = {
        }
        warnings = []
        errors = []
        project_config.require_release_jobs_for_repo(
            deliverable_info,
            {'validate-projects-by-name': zuul_layout},
            'openstack/releases',
            'std',
            warnings.append,
            errors.append,
        )
        self.assertEqual(0, len(warnings))
        self.assertEqual(0, len(errors))

    def test_retired_flag(self):
        deliverable_info = {
            'repository-settings': {
                'openstack/releases': {
                    'flags': [
                        'retired',
                    ]
                }
            }
        }
        zuul_layout = {
        }
        warnings = []
        errors = []
        project_config.require_release_jobs_for_repo(
            deliverable_info,
            {'validate-projects-by-name': zuul_layout},
            'openstack/releases',
            'std',
            warnings.append,
            errors.append,
        )
        self.assertEqual(0, len(warnings))
        self.assertEqual(0, len(errors))

    def test_no_zuul_layout(self):
        deliverable_info = {
        }
        zuul_layout = {
        }
        warnings = []
        errors = []
        project_config.require_release_jobs_for_repo(
            deliverable_info,
            {'validate-projects-by-name': zuul_layout},
            'openstack/releases',
            'std',
            warnings.append,
            errors.append,
        )
        self.assertEqual(0, len(warnings))
        self.assertEqual(1, len(errors))

    def test_one_expected_job(self):
        deliverable_info = {
        }
        zuul_layout = {
            'openstack/releases': {
                'template': [
                    {'name': 'publish-to-pypi'},
                ],
            }
        }
        warnings = []
        errors = []
        project_config.require_release_jobs_for_repo(
            deliverable_info,
            {'validate-projects-by-name': zuul_layout},
            'openstack/releases',
            'std',
            warnings.append,
            errors.append,
        )
        print(warnings, errors)
        self.assertEqual(0, len(warnings))
        self.assertEqual(0, len(errors))

    def test_two_expected_jobs(self):
        deliverable_info = {
        }
        zuul_layout = {
            'openstack/releases': {
                'template': [
                    {'name': 'publish-to-pypi'},
                    {'name': 'puppet-tarball-jobs'},
                ],
            }
        }
        warnings = []
        errors = []
        project_config.require_release_jobs_for_repo(
            deliverable_info,
            {'validate-projects-by-name': zuul_layout},
            'openstack/releases',
            'std',
            warnings.append,
            errors.append,
        )
        self.assertEqual(1, len(warnings))
        self.assertEqual(0, len(errors))
