package com.raykurt.perflab.person;

import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

@Repository
public class PersonRepository {

    private static final String COLUMNS = "id, first_name, last_name, email, city, created_at";

    private static final RowMapper<Person> MAPPER = (rs, rowNum) -> new Person(
            rs.getLong("id"),
            rs.getString("first_name"),
            rs.getString("last_name"),
            rs.getString("email"),
            rs.getString("city"),
            rs.getTimestamp("created_at").toLocalDateTime());

    private final JdbcTemplate jdbc;

    public PersonRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** Primary key lookup: always fast, used as a baseline in the test plan */
    public Optional<Person> findById(long id) {
        List<Person> rows = jdbc.query("SELECT " + COLUMNS + " FROM person WHERE id = ?", MAPPER, id);
        return rows.stream().findFirst();
    }

    /** Slow without an index on email (full table scan), fast after sql/add-index.sql */
    public List<Person> findByEmail(String email) {
        return jdbc.query("SELECT " + COLUMNS + " FROM person WHERE email = ?", MAPPER, email);
    }
}
