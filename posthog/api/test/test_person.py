import json

from django.utils import timezone
from rest_framework import status

from posthog.models import Cohort, Event, Organization, Person, Team
from posthog.tasks.process_event import process_event
from posthog.test.base import APIBaseTest


def test_person_factory(event_factory, person_factory, get_events, get_people):
    class TestPerson(APIBaseTest):
        def test_search(self) -> None:
            person_factory(
                team=self.team, distinct_ids=["distinct_id"], properties={"email": "someone@gmail.com"},
            )
            person_factory(
                team=self.team, distinct_ids=["distinct_id_2"], properties={"email": "another@gmail.com"},
            )
            person_factory(team=self.team, distinct_ids=["distinct_id_3"], properties={})

            response = self.client.get("/api/person/?search=has:email")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 2)

            response = self.client.get("/api/person/?search=another@gm")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 1)

            response = self.client.get("/api/person/?search=_id_3")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 1)

        def test_properties(self) -> None:
            person_factory(
                team=self.team, distinct_ids=["distinct_id"], properties={"email": "someone@gmail.com"},
            )
            person_factory(
                team=self.team, distinct_ids=["distinct_id_2"], properties={"email": "another@gmail.com"},
            )
            person_factory(team=self.team, distinct_ids=["distinct_id_3"], properties={})

            response = self.client.get(
                "/api/person/?properties=%s" % json.dumps([{"key": "email", "operator": "is_set", "value": "is_set"}])
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 2)

            response = self.client.get(
                "/api/person/?properties=%s"
                % json.dumps([{"key": "email", "operator": "icontains", "value": "another@gm"}])
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 1)

        def test_person_property_names(self) -> None:
            person_factory(team=self.team, properties={"$browser": "whatever", "$os": "Mac OS X"})
            person_factory(team=self.team, properties={"random_prop": "asdf"})
            person_factory(team=self.team, properties={"random_prop": "asdf"})

            response = self.client.get("/api/person/properties/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response_data = response.json()
            self.assertEqual(response_data[0]["name"], "random_prop")
            self.assertEqual(response_data[0]["count"], 2)
            self.assertEqual(response_data[2]["name"], "$os")
            self.assertEqual(response_data[2]["count"], 1)
            self.assertEqual(response_data[1]["name"], "$browser")
            self.assertEqual(response_data[1]["count"], 1)

        def test_person_property_values(self):
            person_factory(
                team=self.team, properties={"random_prop": "asdf", "some other prop": "with some text"},
            )
            person_factory(team=self.team, properties={"random_prop": "asdf"})
            person_factory(team=self.team, properties={"random_prop": "qwerty"})
            person_factory(team=self.team, properties={"something_else": "qwerty"})
            response = self.client.get("/api/person/values/?key=random_prop")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response_data = response.json()
            self.assertEqual(response_data[0]["name"], "asdf")
            self.assertEqual(response_data[0]["count"], 2)
            self.assertEqual(response_data[1]["name"], "qwerty")
            self.assertEqual(response_data[1]["count"], 1)
            self.assertEqual(len(response_data), 2)

            response = self.client.get("/api/person/values/?key=random_prop&value=qw")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()[0]["name"], "qwerty")
            self.assertEqual(response.json()[0]["count"], 1)

        def test_filter_by_cohort(self):
            person_factory(
                team=self.team, distinct_ids=["person_1", "anonymous_id"], properties={"$os": "Chrome"},
            )
            person_factory(team=self.team, distinct_ids=["person_2"])

            cohort = Cohort.objects.create(team=self.team, groups=[{"properties": {"$os": "Chrome"}}])
            cohort.calculate_people()
            response = self.client.get(f"/api/person/?cohort={cohort.pk}")
            self.assertEqual(len(response.json()["results"]), 1, response)

        def test_filter_person_list(self):

            person1: Person = person_factory(
                team=self.team, distinct_ids=["distinct_id", "another_one"], properties={"email": "someone@gmail.com"},
            )
            person2: Person = person_factory(
                team=self.team, distinct_ids=["distinct_id_2"], properties={"email": "another@gmail.com"},
            )

            # Filter by distinct ID
            response = self.client.get("/api/person/?distinct_id=distinct_id")  # must be exact matches
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 1)
            self.assertEqual(response.json()["results"][0]["id"], person1.pk)

            response = self.client.get("/api/person/?distinct_id=another_one")  # can search on any of the distinct IDs
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 1)
            self.assertEqual(response.json()["results"][0]["id"], person1.pk)

            # Filter by email
            response = self.client.get("/api/person/?email=another@gmail.com")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 1)
            self.assertEqual(response.json()["results"][0]["id"], person2.pk)

            # Filter by key identifier
            for _identifier in ["another@gmail.com", "distinct_id_2"]:
                response = self.client.get(f"/api/person/?key_identifier={_identifier}")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(len(response.json()["results"]), 1)
                self.assertEqual(response.json()["results"][0]["id"], person2.pk)

            # Non-matches return an empty list
            response = self.client.get("/api/person/?email=inexistent")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 0)

            response = self.client.get("/api/person/?distinct_id=inexistent")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 0)

        def test_cant_see_another_organization_pii_with_filters(self):

            # Completely different organization
            another_org: Organization = Organization.objects.create()
            another_team: Team = Team.objects.create(organization=another_org)
            person_factory(
                team=another_team, distinct_ids=["distinct_id", "x_another_one"],
            )
            person_factory(
                team=another_team, distinct_ids=["x_distinct_id_2"], properties={"email": "team2_another@gmail.com"},
            )

            # Person in current team
            person: Person = person_factory(
                team=self.team, distinct_ids=["distinct_id"],
            )

            # Filter by distinct ID
            response = self.client.get("/api/person/?distinct_id=distinct_id")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 1)
            self.assertEqual(
                response.json()["results"][0]["id"], person.pk,
            )  # note that even with shared distinct IDs, only the person from the same team is returned

            response = self.client.get("/api/person/?distinct_id=x_another_one")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()["results"], [])

            # Filter by key identifier
            for _identifier in ["x_another_one", "distinct_id_2"]:
                response = self.client.get(f"/api/person/?key_identifier={_identifier}")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.json()["results"], [])

        def test_filter_is_identified(self):
            person_anonymous = person_factory(team=self.team, distinct_ids=["xyz"])
            person_identified_already = person_factory(team=self.team, distinct_ids=["tuv"], is_identified=True)
            person_identified_using_event = person_factory(team=self.team, distinct_ids=["klm"])

            # all
            response = self.client.get(
                "/api/person"
            )  # Make sure the endpoint works with and without the trailing slash
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 3)

            # person_identified_using_event should have is_identified set to True after an $identify event
            process_event(
                person_identified_using_event.distinct_ids[0],
                "",
                "",
                {"event": "$identify"},
                self.team.pk,
                timezone.now().isoformat(),
                timezone.now().isoformat(),
            )

            self.assertTrue(get_people()[2].is_identified)
            # anonymous
            response = self.client.get("/api/person/?is_identified=false")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 1)
            self.assertEqual(response.json()["results"][0]["id"], person_anonymous.id)

            # identified
            response = self.client.get("/api/person/?is_identified=true")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.json()["results"]), 2)
            self.assertEqual(response.json()["results"][0]["id"], person_identified_using_event.id)
            self.assertEqual(response.json()["results"][1]["id"], person_identified_already.id)

        def test_delete_person(self):
            person = person_factory(
                team=self.team, distinct_ids=["person_1", "anonymous_id"], properties={"$os": "Chrome"},
            )
            event_factory(event="test", team=self.team, distinct_id="person_1")
            event_factory(event="test", team=self.team, distinct_id="anonymous_id")
            event_factory(event="test", team=self.team, distinct_id="someone_else")

            response = self.client.delete(f"/api/person/{person.pk}/")
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertEqual(response.data, None)
            self.assertEqual(len(get_people()), 0)
            self.assertEqual(len(get_events()), 1)

        def test_filters_by_endpoints_are_deprecated(self):
            person_factory(
                team=self.team, distinct_ids=["person_1"], properties={"email": "someone@gmail.com"},
            )

            # By Distinct ID
            with self.assertWarns(DeprecationWarning) as warnings:
                response = self.client.get("/api/person/by_distinct_id/?distinct_id=person_1")

            self.assertEqual(response.status_code, status.HTTP_200_OK)  # works but it's deprecated
            self.assertEqual(
                str(warnings.warning), "/api/person/by_distinct_id/ endpoint is deprecated; use /api/person/ instead.",
            )

            # By Distinct ID
            with self.assertWarns(DeprecationWarning) as warnings:
                response = self.client.get("/api/person/by_email/?email=someone@gmail.com")

            self.assertEqual(response.status_code, status.HTTP_200_OK)  # works but it's deprecated
            self.assertEqual(
                str(warnings.warning), "/api/person/by_email/ endpoint is deprecated; use /api/person/ instead.",
            )

        def test_filter_id_or_uuid(self) -> None:
            person1 = person_factory(team=self.team, properties={"$browser": "whatever", "$os": "Mac OS X"})
            person2 = person_factory(team=self.team, properties={"random_prop": "asdf"})
            person_factory(team=self.team, properties={"random_prop": "asdf"})

            response = self.client.get("/api/person/?id={},{}".format(person1.id, person2.id))
            response_uuid = self.client.get("/api/person/?uuid={},{}".format(person1.uuid, person2.uuid))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), response_uuid.json())
            self.assertEqual(len(response.json()["results"]), 2)

    return TestPerson


class TestPerson(
    test_person_factory(Event.objects.create, Person.objects.create, Event.objects.all, Person.objects.all)  # type: ignore
):
    pass
